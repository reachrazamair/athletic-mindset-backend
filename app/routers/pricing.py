"""
PRICING ROUTER — public, unauthenticated: the plans shown on the marketing
pricing page (home page #pricing section and /pricing, the same component).
Logged-out visitors need to see this, so unlike assessment/billing there's no
auth dependency here.
"""

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models import PricingPlan
from app.routers.content import _build_locale_map
from app.schemas import ResolvedPricingPlanResponse

router = APIRouter(prefix="/pricing", tags=["pricing"])


@router.get("/plans", response_model=list[ResolvedPricingPlanResponse])
async def list_plans(lang: str = "en", db: AsyncSession = Depends(get_db)):
    """Active plans, text resolved/translated for the requested language."""
    result = await db.execute(
        select(PricingPlan).where(PricingPlan.is_active.is_(True)).order_by(PricingPlan.order)
    )
    plans = result.scalars().all()

    translations = await _build_locale_map(db, lang)

    def _t(key: str, fallback: str) -> str:
        return translations.get(key, fallback)

    resolved: list[ResolvedPricingPlanResponse] = []
    for p in plans:
        prefix = f"pricing.plans.{p.id}."
        resolved.append(
            ResolvedPricingPlanResponse(
                key=p.key,
                name=_t(f"{prefix}name", p.name),
                description=_t(f"{prefix}description", p.description),
                monthly_price_label=_t(f"{prefix}monthly_price_label", p.monthly_price_label),
                monthly_period_label=_t(f"{prefix}monthly_period_label", p.monthly_period_label),
                yearly_price_label=_t(f"{prefix}yearly_price_label", p.yearly_price_label),
                yearly_period_label=_t(f"{prefix}yearly_period_label", p.yearly_period_label),
                note=_t(f"{prefix}note", p.note) if p.note else None,
                features=[_t(f"{prefix}features.{i}", f) for i, f in enumerate(p.features)],
                locked_features=[_t(f"{prefix}locked_features.{i}", f) for i, f in enumerate(p.locked_features)],
                cta_label=_t(f"{prefix}cta_label", p.cta_label),
                featured=p.featured,
            )
        )
    return resolved
