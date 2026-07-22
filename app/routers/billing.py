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
from app.models import PricingPlan, Subscription, SubscriptionPlan, SubscriptionStatus, User
from app.schemas import (
    BillingStatusResponse,
    CheckoutSessionRequest,
    CheckoutSessionResponse,
    PortalSessionResponse,
)

router = APIRouter(prefix="/billing", tags=["billing"])

stripe.api_key = settings.STRIPE_SECRET_KEY


def _checkout_success_url(audience: str) -> str:
    return f"{settings.FRONTEND_URL}/dashboard?checkout=success"


def _checkout_cancel_url(audience: str) -> str:
    if audience in ("athletes", "parents", "coaches"):
        return f"{settings.FRONTEND_URL}/{audience}?checkout=cancelled"
    return f"{settings.FRONTEND_URL}/pricing?checkout=cancelled"


def _require_stripe_configured():
    if not settings.STRIPE_SECRET_KEY:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Billing isn't configured yet.")


async def _get_plan(db: AsyncSession, audience: str, key: str) -> PricingPlan:
    """`key` alone isn't unique across audiences (e.g. "elite" exists for both
    main and parents, at different prices) — always resolve by the pair."""
    result = await db.execute(select(PricingPlan).where(PricingPlan.audience == audience, PricingPlan.key == key))
    plan = result.scalar_one_or_none()
    if plan is None:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Plan not found.")
    return plan


async def _get_or_create_subscription(db: AsyncSession, user: User) -> Subscription:
    result = await db.execute(select(Subscription).where(Subscription.user_id == user.id))
    sub = result.scalar_one_or_none()
    if sub is None:
        sub = Subscription(user_id=user.id)
        db.add(sub)
    return sub


async def _status_response(db: AsyncSession, sub: Subscription | None) -> BillingStatusResponse:
    plan_name = None
    if sub and sub.pricing_plan_id:
        plan = await db.get(PricingPlan, sub.pricing_plan_id)
        plan_name = plan.name if plan else None
    return BillingStatusResponse(
        has_access=has_active_access(sub),
        plan=sub.plan.value if sub else None,
        plan_name=plan_name,
        status=sub.status.value if sub else None,
        current_period_end=sub.current_period_end if sub else None,
        cancel_at_period_end=sub.cancel_at_period_end if sub else False,
        pending_price_notice=sub.pending_price_notice if sub else False,
        pending_monthly_amount_cents=sub.pending_monthly_amount_cents if sub else None,
        pending_yearly_amount_cents=sub.pending_yearly_amount_cents if sub else None,
    )


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
    return await _status_response(db, sub)


@router.post("/checkout-session", response_model=CheckoutSessionResponse)
async def create_checkout_session(
    body: CheckoutSessionRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Start (or resume) a paid subscription purchase for the given (audience, key) plan."""
    _require_stripe_configured()

    plan = await _get_plan(db, body.audience, body.key)
    # Plans that only ever bill annually (matching period labels on both
    # slots, e.g. Coach Team) always use the yearly price, regardless of
    # what billing_period was requested — there's no real monthly offering
    # to fall back to for these.
    is_annual_only = plan.monthly_period_label == plan.yearly_period_label
    price_id = (
        plan.stripe_price_id_yearly
        if is_annual_only or body.billing_period == "yearly"
        else plan.stripe_price_id_monthly
    )
    if not price_id:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="This plan's pricing hasn't been set up in Stripe yet.",
        )

    result = await db.execute(select(Subscription).where(Subscription.user_id == user.id))
    existing = result.scalar_one_or_none()
    existing_customer_id = existing.stripe_customer_id if existing else None

    session_kwargs = dict(
        mode="subscription",
        line_items=[{"price": price_id, "quantity": 1}],
        success_url=_checkout_success_url(plan.audience),
        cancel_url=_checkout_cancel_url(plan.audience),
        client_reference_id=str(user.id),
        metadata={"audience": plan.audience, "key": plan.key},
    )
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
async def billing_status(user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    """The caller's current plan + access state — the frontend uses this to gate the assessment
    and to know whether to show the pending-price-change notice."""
    return await _status_response(db, user.subscription)


@router.post("/acknowledge-price-change", response_model=BillingStatusResponse)
async def acknowledge_price_change(user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    """
    Accept the new price: swaps the subscription to it with no proration (so
    it only applies starting the next invoice, never charged mid-cycle) and
    reverses the cancellation that was scheduled when the notice went out.
    """
    sub = user.subscription
    if sub is None or not sub.pending_price_notice or not sub.stripe_subscription_id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="No pending price change to acknowledge.")

    stripe_sub = stripe.Subscription.retrieve(sub.stripe_subscription_id).to_dict()
    plan = await db.get(PricingPlan, sub.pricing_plan_id) if sub.pricing_plan_id else None
    if plan is None:
        items = stripe_sub.get("items", {}).get("data", [])
        current_product_id = items[0]["price"]["product"] if items else None
        if current_product_id:
            plan_result = await db.execute(select(PricingPlan).where(PricingPlan.stripe_product_id == current_product_id))
            plan = plan_result.scalar_one_or_none()
            if plan is not None:
                sub.pricing_plan_id = plan.id
    if plan is None:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Plan not found.")

    item = stripe_sub["items"]["data"][0]
    interval = item["price"]["recurring"]["interval"]
    is_annual_only = plan.monthly_period_label == plan.yearly_period_label
    new_price_id = plan.stripe_price_id_yearly if is_annual_only or interval == "year" else plan.stripe_price_id_monthly
    if not new_price_id:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="New price isn't set up yet.")

    stripe.Subscription.modify(
        sub.stripe_subscription_id,
        items=[{"id": item["id"], "price": new_price_id}],
        proration_behavior="none",
        cancel_at_period_end=False,
    )
    sub.cancel_at_period_end = False
    sub.pending_price_notice = False
    sub.pending_monthly_amount_cents = None
    sub.pending_yearly_amount_cents = None
    await db.commit()
    await db.refresh(sub)
    return await _status_response(db, sub)


@router.post("/decline-price-change", response_model=BillingStatusResponse)
async def decline_price_change(user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    """Dismiss the notice — the cancel-at-period-end set when it went out already stands, this just stops showing it."""
    sub = user.subscription
    if sub is None or not sub.pending_price_notice:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="No pending price change to decline.")

    sub.pending_price_notice = False
    sub.pending_monthly_amount_cents = None
    sub.pending_yearly_amount_cents = None
    await db.commit()
    await db.refresh(sub)
    return await _status_response(db, sub)


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

    data = event["data"]["object"].to_dict()

    if event["type"] == "checkout.session.completed":
        user_id = data.get("client_reference_id")
        customer_id = data.get("customer")
        subscription_id = data.get("subscription")
        metadata = data.get("metadata") or {}
        audience = metadata.get("audience", "main")
        key = metadata.get("key", "elite")
        if user_id and customer_id and subscription_id:
            plan = await _get_plan(db, audience, key)
            stripe_sub = stripe.Subscription.retrieve(subscription_id).to_dict()
            sub = await _get_or_create_subscription_for_webhook(db, user_id, customer_id)
            sub.plan = SubscriptionPlan(plan.key)
            sub.pricing_plan_id = plan.id
            sub.stripe_customer_id = customer_id
            sub.stripe_subscription_id = subscription_id
            sub.status = SubscriptionStatus(stripe_sub["status"])
            sub.current_period_end = _period_end(stripe_sub)
            sub.cancel_at_period_end = stripe_sub["cancel_at_period_end"]
            # A fresh checkout means they're subscribing anew (e.g. after a
            # previous decline lapsed) — any stale notice from before no longer applies.
            sub.pending_price_notice = False
            sub.pending_monthly_amount_cents = None
            sub.pending_yearly_amount_cents = None
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
