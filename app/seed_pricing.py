"""
SEED PRICING — load the 3 pricing plans shown on the main pricing page.

The copy below is exactly what was previously hardcoded in
src/components/landing/Pricing.tsx, so seeding this doesn't change what
visitors see — it just moves that content into the database so admins can
edit it from the CMS instead of a code change.

Run once (and re-run safely) to populate the plans if the table is empty:
    uv run python -m app.seed_pricing
"""

import stripe
from sqlalchemy import select

from app.config import settings
from app.database import AsyncSessionLocal
from app.models import PricingPlan
from app.pricing_content_sync import format_price_label, sync_plan_content


PLANS = [
    {
        "key": "free",
        "name": "Free",
        "description": "Take the full assessment. See 1 of 8 factors unlocked.",
        "monthly_price_label": "$0",
        "monthly_period_label": "forever",
        "yearly_price_label": "$0",
        "yearly_period_label": "",
        "note": None,
        "features": [
            "Full 22-dimension assessment",
            "1 factor score unlocked (of 8)",
            "Overall Athletic Mindset score",
            "Basic percentile ranking",
            "One assessment per year",
        ],
        "locked_features": [
            "Full 8-factor breakdown",
            "22-dimension detailed scores",
            "Personalized Gameplan",
            "Mental skills routines",
            "Sport-specific benchmarking",
        ],
        "cta_label": "Start Free Assessment",
        "featured": False,
        "order": 0,
    },
    {
        "key": "elite",
        "name": "Elite",
        "description": "Unlock your complete mental performance profile.",
        "monthly_price_label": "$10.42",
        "monthly_period_label": "/mo",
        "yearly_price_label": "$125",
        "yearly_period_label": "/year",
        "note": "Billed as $125/year",
        "features": [
            "Everything in Free, plus:",
            "Full detailed report — all 22 dimensions",
            "Personalized Gameplan with mental skills",
            "Sport-specific benchmarking",
            "Elite athlete comparison",
            "Unlimited reassessments",
            "Parent & Coach report versions",
            "Progress tracking over time",
            "Priority support",
        ],
        "locked_features": [],
        "cta_label": "Get Elite Access",
        "featured": True,
        "order": 1,
    },
    {
        "key": "team",
        "name": "Team",
        "description": "Scale across your entire organization.",
        "monthly_price_label": "Custom",
        "monthly_period_label": "",
        "yearly_price_label": "Custom",
        "yearly_period_label": "",
        "note": None,
        "features": [
            "Everything in Elite, plus:",
            "Bulk athlete onboarding (CSV, links, QR)",
            "Coach dashboard with roster view",
            "Team-level mental readiness analytics",
            "At-risk athlete identification",
            "Team Mindset Assessment included",
            "Partner revenue share program",
            "Dedicated account support",
        ],
        "locked_features": [],
        "cta_label": "Contact Sales",
        "featured": False,
        "order": 2,
    },
]


async def _backfill_elite_stripe_pricing() -> None:
    """
    Populate Elite's stripe_product_id/amounts/price IDs from whatever
    STRIPE_PRICE_ID_MONTHLY/YEARLY are already configured, so the plan starts
    out matching what checkout actually charges instead of the two being
    disconnected. One-time — no-ops once the plan already has this data, so
    it's safe to call on every startup. From then on, admins change the price
    via PATCH /admin/pricing/plans/{id}/price instead of these env vars.
    """
    if not settings.STRIPE_SECRET_KEY or not settings.STRIPE_PRICE_ID_MONTHLY or not settings.STRIPE_PRICE_ID_YEARLY:
        return

    async with AsyncSessionLocal() as db:
        result = await db.execute(select(PricingPlan).where(PricingPlan.key == "elite"))
        plan = result.scalar_one_or_none()
        if plan is None or plan.stripe_price_id_monthly is not None:
            return

        stripe.api_key = settings.STRIPE_SECRET_KEY
        monthly_price = stripe.Price.retrieve(settings.STRIPE_PRICE_ID_MONTHLY)
        yearly_price = stripe.Price.retrieve(settings.STRIPE_PRICE_ID_YEARLY)

        plan.stripe_product_id = monthly_price["product"]
        plan.currency = monthly_price["currency"]
        plan.monthly_amount_cents = monthly_price["unit_amount"]
        plan.yearly_amount_cents = yearly_price["unit_amount"]
        plan.stripe_price_id_monthly = monthly_price["id"]
        plan.stripe_price_id_yearly = yearly_price["id"]
        plan.monthly_price_label = format_price_label(plan.monthly_amount_cents, plan.currency)
        plan.yearly_price_label = format_price_label(plan.yearly_amount_cents, plan.currency)

        await db.flush()
        await sync_plan_content(db, plan)
        await db.commit()
        print("✅ Backfilled Elite plan's Stripe pricing.")


async def ensure_seeded() -> None:
    """Populate the pricing plans if the table is empty. Safe to call on every startup."""
    async with AsyncSessionLocal() as db:
        existing = await db.execute(select(PricingPlan.id).limit(1))
        if existing.scalar_one_or_none() is None:
            for data in PLANS:
                plan = PricingPlan(**data)
                db.add(plan)
                await db.flush()
                await sync_plan_content(db, plan)
            await db.commit()
            print(f"✅ Seeded {len(PLANS)} pricing plans.")

    await _backfill_elite_stripe_pricing()


if __name__ == "__main__":
    import asyncio

    asyncio.run(ensure_seeded())
