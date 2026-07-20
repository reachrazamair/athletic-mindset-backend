"""
PRICING CONTENT SYNC — builds the translatable-text mapping for one pricing
plan and hands it to the shared sync mechanics in app/routers/content.py
(sync_prefixed_content/delete_prefixed_content).

Shared by the admin CRUD router (app/routers/admin_pricing.py — every
create/update/delete) and the seed/startup path (app/seed_pricing.py — so
the initial 3 plans are translatable from first boot).
"""

from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.models import PricingPlan
from app.routers.content import delete_prefixed_content, sync_prefixed_content


async def sync_plan_content(db: AsyncSession, plan: PricingPlan) -> None:
    """Mirror a plan's name, description, price/period labels, note, and feature lists into ContentEntry."""
    items: dict[str, str] = {
        "name": plan.name,
        "description": plan.description,
        "monthly_price_label": plan.monthly_price_label,
        "monthly_period_label": plan.monthly_period_label,
        "yearly_price_label": plan.yearly_price_label,
        "yearly_period_label": plan.yearly_period_label,
        "cta_label": plan.cta_label,
    }
    if plan.note:
        items["note"] = plan.note
    for i, feature in enumerate(plan.features):
        items[f"features.{i}"] = feature
    for i, feature in enumerate(plan.locked_features):
        items[f"locked_features.{i}"] = feature

    await sync_prefixed_content(db, f"pricing.plans.{plan.id}.", items)


async def delete_plan_content(db: AsyncSession, plan_id: UUID) -> None:
    await delete_prefixed_content(db, f"pricing.plans.{plan_id}.")


def format_price_label(amount_cents: int, currency: str = "usd") -> str:
    """1042 -> "$10.42", 0 -> "$0" — whole dollars print without decimals."""
    amount = amount_cents / 100
    symbol = "$" if currency.lower() == "usd" else f"{currency.upper()} "
    if amount == int(amount):
        return f"{symbol}{int(amount)}"
    return f"{symbol}{amount:.2f}"
