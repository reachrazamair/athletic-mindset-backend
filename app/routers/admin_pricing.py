"""
ADMIN PRICING ROUTER — full CRUD, grouped by audience (main pricing page vs
the athlete/parent/coach marketing pages, each with their own tailored plans).

The real Stripe-backed amount (main audience's Elite only) still gets its own
dedicated endpoint below the CRUD: a Stripe Price is immutable, so "changing
the price" means minting a new Price and switching checkout over to it — not
something a plain field update can do.
"""

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
import stripe

from app.config import settings
from app.database import get_db
from app.dependencies import require_role
from app.models import PricingPlan, Subscription, SubscriptionStatus, User
from app.pricing_content_sync import delete_plan_content, format_price_label, sync_plan_content
from app.schemas import (
    MessageResponse,
    PlanPriceUpdateRequest,
    PricingPlanAdminResponse,
    PricingPlanCreate,
    PricingPlanReorderRequest,
    PricingPlanUpdate,
)

router = APIRouter(prefix="/admin/pricing", tags=["admin-pricing"])

stripe.api_key = settings.STRIPE_SECRET_KEY


@router.get("/plans", response_model=list[PricingPlanAdminResponse])
async def list_plans(
    _: User = Depends(require_role("admin")),
    db: AsyncSession = Depends(get_db),
):
    """All plans across every audience — the admin panel groups them client-side."""
    result = await db.execute(select(PricingPlan).order_by(PricingPlan.audience, PricingPlan.order))
    return result.scalars().all()


@router.post("/plans", response_model=PricingPlanAdminResponse, status_code=status.HTTP_201_CREATED)
async def create_plan(
    body: PricingPlanCreate,
    _: User = Depends(require_role("admin")),
    db: AsyncSession = Depends(get_db),
):
    existing = await db.execute(
        select(PricingPlan).where(PricingPlan.audience == body.audience, PricingPlan.key == body.key)
    )
    if existing.scalar_one_or_none() is not None:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="A plan with this key already exists for this audience")

    plan = PricingPlan(**body.model_dump())
    db.add(plan)
    await db.flush()
    await sync_plan_content(db, plan)
    await db.commit()
    await db.refresh(plan)
    return plan


@router.patch("/plans/{plan_id}", response_model=PricingPlanAdminResponse)
async def update_plan(
    plan_id: UUID,
    body: PricingPlanUpdate,
    _: User = Depends(require_role("admin")),
    db: AsyncSession = Depends(get_db),
):
    plan = await db.get(PricingPlan, plan_id)
    if plan is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Plan not found")

    for field, value in body.model_dump(exclude_unset=True).items():
        setattr(plan, field, value)

    await db.flush()
    await sync_plan_content(db, plan)
    await db.commit()
    await db.refresh(plan)
    return plan


@router.delete("/plans/{plan_id}", response_model=MessageResponse)
async def delete_plan(
    plan_id: UUID,
    _: User = Depends(require_role("admin")),
    db: AsyncSession = Depends(get_db),
):
    plan = await db.get(PricingPlan, plan_id)
    if plan is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Plan not found")
    await delete_plan_content(db, plan_id)
    await db.delete(plan)
    await db.commit()
    return MessageResponse(message="Plan deleted.")


@router.patch("/plans/reorder", response_model=MessageResponse)
async def reorder_plans(
    body: PricingPlanReorderRequest,
    _: User = Depends(require_role("admin")),
    db: AsyncSession = Depends(get_db),
):
    for item in body.items:
        plan = await db.get(PricingPlan, item.id)
        if plan is not None:
            plan.order = item.order
    await db.commit()
    return MessageResponse(message="Order updated.")


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
                Subscription.pricing_plan_id == plan.id,
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
