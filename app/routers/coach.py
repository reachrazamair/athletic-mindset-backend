"""
COACH ROUTER — Partner Program referral code (step 1: attribution only).

GET /coach/referral → this coach's shareable referral code/link + how many
athletes have signed up through it so far. No commission/payout math here —
that's a later stage once this attribution foundation is proven out.
"""

import secrets

from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.database import get_db
from app.dependencies import require_role
from app.models import CoachReferral, User
from app.schemas import CoachReferralResponse

router = APIRouter(prefix="/coach", tags=["coach"])


async def _generate_unique_code(db: AsyncSession) -> str:
    """8-char URL-safe code; retry on the rare unique-constraint collision."""
    while True:
        code = secrets.token_urlsafe(6)[:8]
        existing = await db.execute(select(User.id).where(User.referral_code == code))
        if existing.scalar_one_or_none() is None:
            return code


@router.get("/referral", response_model=CoachReferralResponse)
async def get_referral(
    user: User = Depends(require_role("coach")),
    db: AsyncSession = Depends(get_db),
):
    if user.referral_code is None:
        user.referral_code = await _generate_unique_code(db)
        await db.commit()
        await db.refresh(user)

    count_result = await db.execute(
        select(func.count()).select_from(CoachReferral).where(CoachReferral.coach_user_id == user.id)
    )
    total_referred = count_result.scalar_one()

    return CoachReferralResponse(
        code=user.referral_code,
        referral_link=f"{settings.FRONTEND_URL}/signup?ref={user.referral_code}",
        total_referred=total_referred,
    )
