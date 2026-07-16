"""
PROFILE ROUTER — Athlete demographic profile (captured during onboarding).

GET /profile   → the current user's athlete profile (or null fields if none yet)
PUT /profile   → create or update the profile
"""

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies import get_current_user
from app.models import AthleteProfile, User
from app.schemas import AthleteProfileResponse, AthleteProfileUpdate

router = APIRouter(prefix="/profile", tags=["profile"])


@router.get("", response_model=AthleteProfileResponse)
async def get_profile(user: User = Depends(get_current_user)):
    """Return the current user's athlete profile (empty fields if not set yet)."""
    if user.athlete_profile is None:
        return AthleteProfileResponse(
            birth_date=None,
            sex=None,
            ethnicity=None,
            primary_sport=None,
            competition_level=None,
            position=None,
            sport_category=None,
        )
    return AthleteProfileResponse.model_validate(user.athlete_profile)


@router.put("", response_model=AthleteProfileResponse)
async def upsert_profile(
    body: AthleteProfileUpdate,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Create or update the current user's athlete profile."""
    result = await db.execute(
        select(AthleteProfile).where(AthleteProfile.user_id == user.id)
    )
    profile = result.scalar_one_or_none()

    if profile is None:
        profile = AthleteProfile(user_id=user.id)
        db.add(profile)

    # Apply only the provided fields.
    data = body.model_dump(exclude_unset=True)
    for field, value in data.items():
        setattr(profile, field, value)

    await db.commit()
    await db.refresh(profile)

    return AthleteProfileResponse.model_validate(profile)
