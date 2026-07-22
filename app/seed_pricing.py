"""
SEED PRICING — load the pricing plans shown across the site: the main
pricing page (home #pricing + /pricing) plus the tailored plans shown on the
athlete/parent/coach marketing pages.

The copy below is exactly what was previously hardcoded in each page's own
component (src/components/landing/Pricing.tsx, athletes/AthletePricing.tsx,
parents/ParentPricing.tsx, coaches/CoachPricing.tsx), so seeding this doesn't
change what visitors see — it just moves that content into the database so
admins can edit it from the CMS instead of a code change. "main", "athletes",
and "parents" Elite carry real Stripe pricing; coach is still marketing-only
for now.

Run once (and re-run safely) to populate the plans if the table is empty:
    uv run python -m app.seed_pricing
"""

import stripe
from sqlalchemy import select

from app.config import settings
from app.database import AsyncSessionLocal
from app.models import PricingPlan
from app.pricing_content_sync import format_price_label, sync_plan_content


MAIN_PLANS = [
    {
        "audience": "main",
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
        "audience": "main",
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
        "audience": "main",
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

ATHLETE_PLANS = [
    {
        "audience": "athletes",
        "key": "free",
        "name": "Free",
        "description": "See where you stand — 1 factor unlocked",
        "monthly_price_label": "$0",
        "monthly_period_label": "",
        "yearly_price_label": "$0",
        "yearly_period_label": "",
        "note": None,
        "features": [
            "Full 22-dimension assessment",
            "1 factor score unlocked (of 8)",
            "Overall Athletic Mindset score",
            "Basic percentile ranking",
        ],
        "locked_features": [
            "Full 8-factor detailed breakdown",
            "Personalized Gameplan",
            "Mental skills routines",
            "Sport-specific benchmarking",
        ],
        "cta_label": "Start Free",
        "cta_href": "/assessment",
        "featured": False,
        "order": 0,
    },
    {
        "audience": "athletes",
        "key": "elite",
        "name": "Elite Report",
        "description": "The complete mental performance experience",
        "monthly_price_label": "$10.42",
        "monthly_period_label": "/mo",
        "yearly_price_label": "$125",
        "yearly_period_label": "/year",
        "note": None,
        "features": [
            "Everything in Free, plus:",
            "Full detailed report — all 22 dimensions",
            "Personalized Gameplan with mental skills",
            "Sport-specific benchmarking",
            "Elite athlete comparison (D1/Pro)",
            "7 Situational Mindset profiles",
            "Unlimited reassessments",
            "Progress tracking over time",
            "Parent & Coach report included",
        ],
        "locked_features": [],
        "cta_label": "Get Elite Report",
        "cta_href": "#buy",
        "featured": True,
        "order": 1,
    },
]

PARENT_PLANS = [
    {
        "audience": "parents",
        "key": "free",
        "name": "Free",
        "description": "See where your athlete stands — 1 factor unlocked",
        "monthly_price_label": "$0",
        "monthly_period_label": "",
        "yearly_price_label": "$0",
        "yearly_period_label": "",
        "note": None,
        "features": [
            "Full 22-dimension assessment",
            "1 factor score unlocked (of 8)",
            "Overall Athletic Mindset score",
            "Basic percentile ranking",
        ],
        "locked_features": [
            "Full Parent Gameplan report",
            "Communication & support guidance",
            "8-factor detailed breakdown",
            "Progress tracking over time",
        ],
        "cta_label": "Start Free",
        "cta_href": "/assessment",
        "featured": False,
        "order": 0,
    },
    {
        "audience": "parents",
        "key": "elite",
        "name": "Athlete + Parent Elite",
        "description": "The complete report for your athlete — and for you.",
        "monthly_price_label": "$15",
        "monthly_period_label": "/mo",
        "yearly_price_label": "$175",
        "yearly_period_label": "/year",
        "note": None,
        "features": [
            "Everything in Free, plus:",
            "Full Athlete Report — all 22 dimensions",
            "Dedicated Parent Gameplan report",
            "Plain-language communication guidance",
            "How to support without undermining the coach",
            "Sport-specific benchmarking",
            "Unlimited reassessments",
            "Progress tracking over time",
        ],
        "locked_features": [],
        "cta_label": "Get Athlete + Parent Elite",
        "cta_href": "#pricing",
        "featured": True,
        "order": 1,
    },
]

COACH_PLANS = [
    {
        "audience": "coaches",
        "key": "free",
        "name": "Coach Free",
        "description": "Try it with a few of your athletes",
        "monthly_price_label": "$0",
        "monthly_period_label": "",
        "yearly_price_label": "$0",
        "yearly_period_label": "",
        "note": None,
        "features": [
            "Invite up to 3 athletes",
            "Coach report for each athlete",
            "Basic roster view",
            "One team snapshot",
        ],
        "locked_features": [
            "Full Team Mindset report",
            "Unlimited athletes & teams",
            "At-risk athlete alerts",
            "Season-long progress tracking",
        ],
        "cta_label": "Start Free",
        "cta_href": "/signup",
        "featured": False,
        "order": 0,
    },
    {
        "audience": "coaches",
        "key": "team",
        "name": "Team",
        "description": "Everything your roster needs, all season",
        # No monthly/yearly toggle on this page — one price shown either way.
        "monthly_price_label": "$499",
        "monthly_period_label": "/year · billed annually",
        "yearly_price_label": "$499",
        "yearly_period_label": "/year · billed annually",
        "note": None,
        "features": [
            "Everything in Free, plus:",
            "Coach report for every athlete",
            "Full Team Mindset report",
            "Coach Summary across your roster",
            "At-risk athlete detection",
            "Unlimited teams",
            "Season-long progress tracking",
            "Priority support",
        ],
        "locked_features": [],
        "cta_label": "Get Team Access",
        "cta_href": None,
        "featured": True,
        "order": 1,
    },
]

ALL_PLANS = MAIN_PLANS + ATHLETE_PLANS + PARENT_PLANS + COACH_PLANS


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
        result = await db.execute(
            select(PricingPlan).where(PricingPlan.audience == "main", PricingPlan.key == "elite")
        )
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
        print("Backfilled Elite plan's Stripe pricing.")


async def _backfill_parent_elite_stripe_pricing() -> None:
    """
    Parents' Elite has no pre-existing Stripe Price to adopt (unlike main's,
    which reuses whatever STRIPE_PRICE_ID_MONTHLY/YEARLY were already set up)
    — so this creates a brand-new Product + monthly/yearly Prices under the
    same Stripe account. One-time — no-ops once the plan already has this
    data. From then on, admins change the price via
    PATCH /admin/pricing/plans/{id}/price instead of this script.
    """
    if not settings.STRIPE_SECRET_KEY:
        return

    async with AsyncSessionLocal() as db:
        result = await db.execute(
            select(PricingPlan).where(PricingPlan.audience == "parents", PricingPlan.key == "elite")
        )
        plan = result.scalar_one_or_none()
        if plan is None or plan.stripe_product_id is not None:
            return

        stripe.api_key = settings.STRIPE_SECRET_KEY
        product = stripe.Product.create(name=plan.name)
        monthly_price = stripe.Price.create(
            product=product.id, unit_amount=1500, currency="usd", recurring={"interval": "month"}
        )
        yearly_price = stripe.Price.create(
            product=product.id, unit_amount=17500, currency="usd", recurring={"interval": "year"}
        )

        plan.stripe_product_id = product.id
        plan.currency = "usd"
        plan.monthly_amount_cents = monthly_price["unit_amount"]
        plan.yearly_amount_cents = yearly_price["unit_amount"]
        plan.stripe_price_id_monthly = monthly_price["id"]
        plan.stripe_price_id_yearly = yearly_price["id"]
        plan.monthly_price_label = format_price_label(plan.monthly_amount_cents, plan.currency)
        plan.yearly_price_label = format_price_label(plan.yearly_amount_cents, plan.currency)

        await db.flush()
        await sync_plan_content(db, plan)
        await db.commit()
        print("Created Stripe Product/Prices for Parents' Elite plan.")


async def _backfill_athlete_elite_stripe_pricing() -> None:
    """
    Athletes' Elite needs its own Stripe Product/Prices so subscriptions on
    the athlete audience can be tracked separately from main pricing and can
    receive audience-specific price-change notices.
    """
    if not settings.STRIPE_SECRET_KEY:
        return

    async with AsyncSessionLocal() as db:
        result = await db.execute(
            select(PricingPlan).where(PricingPlan.audience == "athletes", PricingPlan.key == "elite")
        )
        plan = result.scalar_one_or_none()
        if plan is None or plan.stripe_product_id is not None:
            return

        stripe.api_key = settings.STRIPE_SECRET_KEY
        product = stripe.Product.create(name=plan.name)
        monthly_price = stripe.Price.create(
            product=product.id, unit_amount=1042, currency="usd", recurring={"interval": "month"}
        )
        yearly_price = stripe.Price.create(
            product=product.id, unit_amount=12500, currency="usd", recurring={"interval": "year"}
        )

        plan.stripe_product_id = product.id
        plan.currency = "usd"
        plan.monthly_amount_cents = monthly_price["unit_amount"]
        plan.yearly_amount_cents = yearly_price["unit_amount"]
        plan.stripe_price_id_monthly = monthly_price["id"]
        plan.stripe_price_id_yearly = yearly_price["id"]
        plan.monthly_price_label = format_price_label(plan.monthly_amount_cents, plan.currency)
        plan.yearly_price_label = format_price_label(plan.yearly_amount_cents, plan.currency)

        await db.flush()
        await sync_plan_content(db, plan)
        await db.commit()
        print("Created Stripe Product/Prices for Athletes' Elite plan.")


async def _backfill_coach_team_stripe_pricing() -> None:
    """
    Coach Team is billed annually only — the page has no monthly/yearly
    toggle, both labels already show the same $499/year figure. Mints one
    Stripe Price (interval=year) and reuses it for both the monthly and
    yearly slots, so checkout resolves correctly regardless of which
    billing_period the frontend happens to send. One-time — no-ops once the
    plan already has this data.
    """
    if not settings.STRIPE_SECRET_KEY:
        return

    async with AsyncSessionLocal() as db:
        result = await db.execute(
            select(PricingPlan).where(PricingPlan.audience == "coaches", PricingPlan.key == "team")
        )
        plan = result.scalar_one_or_none()
        if plan is None or plan.stripe_product_id is not None:
            return

        stripe.api_key = settings.STRIPE_SECRET_KEY
        product = stripe.Product.create(name=plan.name)
        price = stripe.Price.create(
            product=product.id, unit_amount=49900, currency="usd", recurring={"interval": "year"}
        )

        plan.stripe_product_id = product.id
        plan.currency = "usd"
        plan.monthly_amount_cents = price["unit_amount"]
        plan.yearly_amount_cents = price["unit_amount"]
        plan.stripe_price_id_monthly = price["id"]
        plan.stripe_price_id_yearly = price["id"]
        plan.monthly_price_label = format_price_label(plan.monthly_amount_cents, plan.currency)
        plan.yearly_price_label = format_price_label(plan.yearly_amount_cents, plan.currency)

        await db.flush()
        await sync_plan_content(db, plan)
        await db.commit()
        print("Created Stripe Product/Price for Coach Team plan.")


async def ensure_seeded() -> None:
    """
    Populate any audience's plans that aren't seeded yet — checked
    per-audience (not "is the table empty") so adding a brand-new audience
    later seeds just that one without touching audiences already seeded and
    since admin-edited. Safe to call on every startup.
    """
    async with AsyncSessionLocal() as db:
        for data_list in (MAIN_PLANS, ATHLETE_PLANS, PARENT_PLANS, COACH_PLANS):
            audience = data_list[0]["audience"]
            existing = await db.execute(select(PricingPlan.id).where(PricingPlan.audience == audience).limit(1))
            if existing.scalar_one_or_none() is not None:
                continue
            for data in data_list:
                plan = PricingPlan(**data)
                db.add(plan)
                await db.flush()
                await sync_plan_content(db, plan)
            print(f"Seeded {len(data_list)} pricing plans for audience '{audience}'.")
        await db.commit()

    await _backfill_elite_stripe_pricing()
    await _backfill_athlete_elite_stripe_pricing()
    await _backfill_parent_elite_stripe_pricing()
    await _backfill_coach_team_stripe_pricing()


if __name__ == "__main__":
    import asyncio

    asyncio.run(ensure_seeded())
