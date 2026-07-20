"""
ADMIN PRICING ROUTER.

Plan text (name, description, features, price labels, ...) is edited through
the normal CMS Content editor — sync_plan_content already mirrors every
plan's fields into ContentEntry, and the resolved athlete-facing endpoint
always prefers a ContentEntry value over the raw column, so no separate CRUD
UI is needed for that.

What *does* need a dedicated endpoint is the real Stripe-backed amount: a
Stripe Price is immutable, so "changing the price" means minting a new Price
and switching checkout over to it — not something a plain text edit can do.
"""

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
import stripe

from app.config import settings
from app.database import get_db
from app.dependencies import require_role
from app.models import PricingPlan, Subscription, SubscriptionPlan, SubscriptionStatus, User
from app.pricing_content_sync import format_price_label, sync_plan_content
from app.schemas import PlanPriceUpdateRequest, PricingPlanAdminResponse

router = APIRouter(prefix="/admin/pricing", tags=["admin-pricing"])

stripe.api_key = settings.STRIPE_SECRET_KEY


@router.get("/plans", response_model=list[PricingPlanAdminResponse])
async def list_plans(
    _: User = Depends(require_role("admin")),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(PricingPlan).order_by(PricingPlan.order))
    return result.scalars().all()


@router.patch("/plans/{plan_id}/price", response_model=PricingPlanAdminResponse)
async def update_plan_price(
    plan_id: UUID,
    body: PlanPriceUpdateRequest,
    _: User = Depends(require_role("admin")),
    db: AsyncSession = Depends(get_db),
):
    """
    Change what this plan actually charges. For each period whose amount
    changed, mints a brand-new Stripe Price under the plan's product (Prices
    can't be edited in place) and points future checkouts at it — existing
    subscribers stay on whatever price they originally signed up for, same
    as Stripe's own default behavior. The display label is regenerated from
    the new amount, so it can never drift from what's actually charged.
    """
    if not settings.STRIPE_SECRET_KEY:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Stripe isn't configured yet.")

    plan = await db.get(PricingPlan, plan_id)
    if plan is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Plan not found")
    if not plan.stripe_product_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="This plan has no Stripe product yet — it can't be priced through this endpoint.",
        )

    if body.monthly_amount_cents != plan.monthly_amount_cents:
        price = stripe.Price.create(
            product=plan.stripe_product_id,
            unit_amount=body.monthly_amount_cents,
            currency=plan.currency,
            recurring={"interval": "month"},
        )
        plan.stripe_price_id_monthly = price.id
        plan.monthly_amount_cents = body.monthly_amount_cents
        plan.monthly_price_label = format_price_label(body.monthly_amount_cents, plan.currency)

    if body.yearly_amount_cents != plan.yearly_amount_cents:
        price = stripe.Price.create(
            product=plan.stripe_product_id,
            unit_amount=body.yearly_amount_cents,
            currency=plan.currency,
            recurring={"interval": "year"},
        )
        plan.stripe_price_id_yearly = price.id
        plan.yearly_amount_cents = body.yearly_amount_cents
        plan.yearly_price_label = format_price_label(body.yearly_amount_cents, plan.currency)

    if body.notify_existing_subscribers:
        subs_result = await db.execute(
            select(Subscription).where(
                Subscription.plan == SubscriptionPlan(plan.key),
                Subscription.status.in_([SubscriptionStatus.active, SubscriptionStatus.trialing]),
                Subscription.stripe_subscription_id.isnot(None),
            )
        )
        for sub in subs_result.scalars().all():
            # Safe default: access continues through what they already paid
            # for, then lapses — unless they acknowledge (see
            # POST /billing/acknowledge-price-change), which swaps them to
            # the new price and reverses this.
            stripe.Subscription.modify(sub.stripe_subscription_id, cancel_at_period_end=True)
            sub.cancel_at_period_end = True
            sub.pending_price_notice = True
            sub.pending_monthly_amount_cents = plan.monthly_amount_cents
            sub.pending_yearly_amount_cents = plan.yearly_amount_cents

    await db.flush()
    await sync_plan_content(db, plan)
    await db.commit()
    await db.refresh(plan)
    return plan
