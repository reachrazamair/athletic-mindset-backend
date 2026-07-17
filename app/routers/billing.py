"""
BILLING ROUTER — Free plan grant + Stripe Checkout/Portal for Elite + webhook sync.

POST /billing/subscribe-free     → grant the free plan directly (no Stripe)
POST /billing/checkout-session   → start (or resume) an Elite subscription purchase
POST /billing/portal-session     → manage/cancel an existing Stripe subscription
GET  /billing/status             → the caller's current plan + access state
POST /billing/webhook            → Stripe's server-to-server event feed (no user auth)

Paid-plan Subscription rows are never written to from the user-facing
endpoints below — only the webhook handler mutates them, driven entirely by
what Stripe reports. That keeps our copy of "who has paid" honest even if a
browser tab closes mid-checkout or a payment later fails.
"""

from datetime import datetime, timezone

import stripe
from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.billing import has_active_access
from app.config import settings
from app.database import get_db
from app.dependencies import get_current_user
from app.models import Subscription, SubscriptionPlan, SubscriptionStatus, User
from app.schemas import (
    BillingStatusResponse,
    CheckoutSessionRequest,
    CheckoutSessionResponse,
    PortalSessionResponse,
)

router = APIRouter(prefix="/billing", tags=["billing"])

stripe.api_key = settings.STRIPE_SECRET_KEY

PRICE_IDS = {
    "monthly": settings.STRIPE_PRICE_ID_MONTHLY,
    "yearly": settings.STRIPE_PRICE_ID_YEARLY,
}


def _require_stripe_configured():
    if not settings.STRIPE_SECRET_KEY or not settings.STRIPE_PRICE_ID_MONTHLY or not settings.STRIPE_PRICE_ID_YEARLY:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Billing isn't configured yet — set STRIPE_SECRET_KEY, STRIPE_PRICE_ID_MONTHLY and STRIPE_PRICE_ID_YEARLY.",
        )


async def _get_or_create_subscription(db: AsyncSession, user: User) -> Subscription:
    result = await db.execute(select(Subscription).where(Subscription.user_id == user.id))
    sub = result.scalar_one_or_none()
    if sub is None:
        sub = Subscription(user_id=user.id)
        db.add(sub)
    return sub


@router.post("/subscribe-free", response_model=BillingStatusResponse)
async def subscribe_free(user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    """Grant the free plan directly — no payment, no Stripe subscription. A Stripe
    customer is created opportunistically (if keys are configured) so an
    upgrade to Elite later can reuse it; not required for the free plan itself."""
    sub = await _get_or_create_subscription(db, user)

    # Never downgrade an existing paid plan back to free.
    if sub.status not in (SubscriptionStatus.active, SubscriptionStatus.trialing) or sub.plan == SubscriptionPlan.free:
        sub.plan = SubscriptionPlan.free
        sub.status = SubscriptionStatus.active
        if sub.stripe_customer_id is None and settings.STRIPE_SECRET_KEY:
            customer = stripe.Customer.create(email=user.email)
            sub.stripe_customer_id = customer.id

    await db.commit()
    await db.refresh(sub)
    return BillingStatusResponse(
        has_access=has_active_access(sub),
        plan=sub.plan.value,
        status=sub.status.value,
        current_period_end=sub.current_period_end,
        cancel_at_period_end=sub.cancel_at_period_end,
    )


@router.post("/checkout-session", response_model=CheckoutSessionResponse)
async def create_checkout_session(
    body: CheckoutSessionRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Start (or resume) the Elite subscription purchase."""
    _require_stripe_configured()

    result = await db.execute(select(Subscription).where(Subscription.user_id == user.id))
    existing = result.scalar_one_or_none()
    existing_customer_id = existing.stripe_customer_id if existing else None

    session_kwargs = dict(
        mode="subscription",
        line_items=[{"price": PRICE_IDS[body.billing_period], "quantity": 1}],
        success_url=f"{settings.FRONTEND_URL}/assessment?checkout=success",
        cancel_url=f"{settings.FRONTEND_URL}/pricing?checkout=cancelled",
        client_reference_id=str(user.id),
        metadata={"plan": "elite"},
    )
    # Reuse the same Stripe customer on a repeat purchase (e.g. upgrading from
    # the free plan, or resubscribing after a cancellation) instead of letting
    # Stripe mint a duplicate one.
    if existing_customer_id:
        session_kwargs["customer"] = existing_customer_id
    else:
        session_kwargs["customer_email"] = user.email

    checkout_session = stripe.checkout.Session.create(**session_kwargs)
    return CheckoutSessionResponse(checkout_url=checkout_session.url)


@router.post("/portal-session", response_model=PortalSessionResponse)
async def create_portal_session(user: User = Depends(get_current_user)):
    """Send an already-subscribed athlete to Stripe's hosted portal to update payment or cancel."""
    _require_stripe_configured()
    if user.subscription is None or not user.subscription.stripe_customer_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No Stripe subscription on file")

    portal_session = stripe.billing_portal.Session.create(
        customer=user.subscription.stripe_customer_id,
        return_url=f"{settings.FRONTEND_URL}/dashboard",
    )
    return PortalSessionResponse(portal_url=portal_session.url)


@router.get("/status", response_model=BillingStatusResponse)
async def billing_status(user: User = Depends(get_current_user)):
    """The caller's current plan + access state — the frontend uses this to gate the assessment."""
    sub = user.subscription
    return BillingStatusResponse(
        has_access=has_active_access(sub),
        plan=sub.plan.value if sub else None,
        status=sub.status.value if sub else None,
        current_period_end=sub.current_period_end if sub else None,
        cancel_at_period_end=sub.cancel_at_period_end if sub else False,
    )


def _period_end(subscription_object: dict) -> datetime | None:
    """current_period_end moved off the Subscription object onto each item as of
    Stripe API 2025-03-31 (Basil) — it's no longer set at the top level."""
    items = (subscription_object.get("items") or {}).get("data") or []
    if not items or items[0].get("current_period_end") is None:
        return None
    return datetime.fromtimestamp(items[0]["current_period_end"], tz=timezone.utc)


async def _get_or_create_subscription_for_webhook(db: AsyncSession, user_id: str, customer_id: str) -> Subscription:
    result = await db.execute(select(Subscription).where(Subscription.user_id == user_id))
    sub = result.scalar_one_or_none()
    if sub is None:
        sub = Subscription(user_id=user_id, stripe_customer_id=customer_id)
        db.add(sub)
    return sub


@router.post("/webhook")
async def stripe_webhook(request: Request, db: AsyncSession = Depends(get_db)):
    """Stripe calls this directly — verified via signature, not user-authenticated."""
    if not settings.STRIPE_WEBHOOK_SECRET:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Webhook secret not configured")

    payload = await request.body()
    sig_header = request.headers.get("stripe-signature", "")
    try:
        event = stripe.Webhook.construct_event(payload, sig_header, settings.STRIPE_WEBHOOK_SECRET)
    except (ValueError, stripe.SignatureVerificationError):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid webhook signature")

    # Stripe's SDK objects don't support dict-style .get() the way they look
    # like they should (it raises AttributeError) — converting to a plain
    # dict up front avoids that trap for the rest of this handler.
    data = event["data"]["object"].to_dict()

    if event["type"] == "checkout.session.completed":
        user_id = data.get("client_reference_id")
        customer_id = data.get("customer")
        subscription_id = data.get("subscription")
        plan = (data.get("metadata") or {}).get("plan", "elite")
        if user_id and customer_id and subscription_id:
            stripe_sub = stripe.Subscription.retrieve(subscription_id).to_dict()
            sub = await _get_or_create_subscription_for_webhook(db, user_id, customer_id)
            sub.plan = SubscriptionPlan(plan)
            sub.stripe_customer_id = customer_id
            sub.stripe_subscription_id = subscription_id
            sub.status = SubscriptionStatus(stripe_sub["status"])
            sub.current_period_end = _period_end(stripe_sub)
            sub.cancel_at_period_end = stripe_sub["cancel_at_period_end"]
            await db.commit()

    elif event["type"] in ("customer.subscription.updated", "customer.subscription.deleted"):
        subscription_id = data.get("id")
        result = await db.execute(select(Subscription).where(Subscription.stripe_subscription_id == subscription_id))
        sub = result.scalar_one_or_none()
        if sub is not None:
            sub.status = SubscriptionStatus(data["status"])
            sub.current_period_end = _period_end(data)
            sub.cancel_at_period_end = data["cancel_at_period_end"]
            await db.commit()

    return {"received": True}
