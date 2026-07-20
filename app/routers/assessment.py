"""
ASSESSMENT ROUTER — athlete-facing: take the assessment, one question at a time.

GET  /assessment/questions          → active questions for a tier, text resolved for the caller
POST /assessment/sessions           → start (or resume) a session for a tier
GET  /assessment/sessions/current   → the caller's current session + ratings so far, for resume
PUT    /assessment/sessions/{id}/ratings    → upsert one question's full set of option ratings
POST   /assessment/sessions/{id}/complete   → mark a session finished
DELETE /assessment/sessions/{id}            → discard an in-progress attempt and its ratings

Every current question is "rate every option" (response_mode = rate_all): the
athlete rates each option's effectiveness 1-5 rather than picking one. No
scoring happens here — ratings are stored as-is for a later reporting pass.
"""

from collections import defaultdict
from datetime import datetime, timezone
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.billing import require_active_subscription
from app.database import get_db
from app.dependencies import get_current_user
from app.models import (
    AssessmentQuestion,
    AssessmentResponse,
    AssessmentSession,
    AssessmentSessionStatus,
    QuestionTierEnum,
    User,
)
from app.routers.content import _build_locale_map
from app.schemas import (
    AssessmentSessionCurrentResponse,
    AssessmentSessionRatingRequest,
    AssessmentSessionRequest,
    AssessmentSessionResponse,
    MessageResponse,
    ResolvedOptionResponse,
    ResolvedQuestionResponse,
)

router = APIRouter(prefix="/assessment", tags=["assessment"])


@router.get("/questions", response_model=list[ResolvedQuestionResponse])
async def list_questions(
    tier: str = "free",
    lang: str = "en",
    user: User = Depends(require_active_subscription),
    db: AsyncSession = Depends(get_db),
):
    """Active questions for a tier, with prompt text translated to the requested language."""
    result = await db.execute(
        select(AssessmentQuestion)
        .options(selectinload(AssessmentQuestion.options))
        .where(AssessmentQuestion.is_active.is_(True), AssessmentQuestion.tier == QuestionTierEnum(tier))
        .order_by(AssessmentQuestion.order)
    )
    questions = result.scalars().all()

    # Question/option text is admin-authored content, translated the same way
    # as the rest of the site's copy: an English master ContentEntry row per
    # key, auto-translated into any language on first request. Keys look like
    #   assessment.questions.{question_id}.prompt
    #   assessment.questions.{question_id}.options.{option_id}.text
    # (admin_assessment.py keeps these rows in sync whenever a question is saved).
    translations = await _build_locale_map(db, lang)

    def _t(key: str, fallback: str) -> str:
        return translations.get(key, fallback)

    resolved: list[ResolvedQuestionResponse] = []
    for q in questions:
        resolved.append(
            ResolvedQuestionResponse(
                id=q.id,
                order=q.order,
                prompt=_t(f"assessment.questions.{q.id}.prompt", q.prompt),
                helper_text=_t(
                    f"assessment.questions.{q.id}.helper_text",
                    q.helper_text or "",
                ) or None,
                question_type=q.question_type.value,
                measurement_type=q.measurement_type.value,
                response_mode=q.response_mode.value,
                options=[
                    ResolvedOptionResponse(
                        id=o.id,
                        label=o.label,
                        text=_t(f"assessment.questions.{q.id}.options.{o.id}.text", o.text),
                    )
                    for o in q.options
                ],
            )
        )
    return resolved


@router.post("/sessions", response_model=AssessmentSessionResponse, status_code=status.HTTP_201_CREATED)
async def start_or_resume_session(
    body: AssessmentSessionRequest,
    user: User = Depends(require_active_subscription),
    db: AsyncSession = Depends(get_db),
):
    """Return the caller's in-progress session for this tier, or create one."""
    tier = QuestionTierEnum(body.tier)
    result = await db.execute(
        select(AssessmentSession).where(
            AssessmentSession.user_id == user.id,
            AssessmentSession.tier == tier,
            AssessmentSession.status == AssessmentSessionStatus.in_progress,
        )
    )
    session = result.scalar_one_or_none()

    if session is None:
        session = AssessmentSession(user_id=user.id, tier=tier)
        db.add(session)
        await db.commit()
        await db.refresh(session)

    return AssessmentSessionResponse.model_validate(session)


@router.get("/sessions/current", response_model=AssessmentSessionCurrentResponse)
async def get_current_session(
    tier: str = "free",
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """The caller's most recent session for a tier (in-progress or completed) plus its ratings so far."""
    result = await db.execute(
        select(AssessmentSession)
        .where(AssessmentSession.user_id == user.id, AssessmentSession.tier == QuestionTierEnum(tier))
        .order_by(AssessmentSession.started_at.desc())
    )
    session = result.scalars().first()

    if session is None:
        return AssessmentSessionCurrentResponse(session=None, ratings={})

    responses_result = await db.execute(
        select(AssessmentResponse).where(AssessmentResponse.session_id == session.id)
    )
    ratings: dict[UUID, dict[UUID, int]] = defaultdict(dict)
    for r in responses_result.scalars().all():
        if r.rating is not None:
            ratings[r.question_id][r.option_id] = r.rating

    return AssessmentSessionCurrentResponse(
        session=AssessmentSessionResponse.model_validate(session),
        ratings=dict(ratings),
    )


async def _get_owned_session(db: AsyncSession, session_id: UUID, user: User) -> AssessmentSession:
    result = await db.execute(select(AssessmentSession).where(AssessmentSession.id == session_id))
    session = result.scalar_one_or_none()
    if session is None or session.user_id != user.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Session not found")
    return session


@router.put("/sessions/{session_id}/ratings", response_model=AssessmentSessionResponse)
async def submit_ratings(
    session_id: UUID,
    body: AssessmentSessionRatingRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Upsert the caller's effectiveness ratings for every option of one question."""
    session = await _get_owned_session(db, session_id, user)
    if session.status != AssessmentSessionStatus.in_progress:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="This session is already completed")

    existing_result = await db.execute(
        select(AssessmentResponse).where(
            AssessmentResponse.session_id == session.id,
            AssessmentResponse.question_id == body.question_id,
        )
    )
    existing_by_option = {r.option_id: r for r in existing_result.scalars().all()}

    for option_id, rating in body.ratings.items():
        existing = existing_by_option.get(option_id)
        if existing is None:
            db.add(AssessmentResponse(
                session_id=session.id, question_id=body.question_id, option_id=option_id, rating=rating,
            ))
        else:
            existing.rating = rating

    await db.commit()
    await db.refresh(session)
    return AssessmentSessionResponse.model_validate(session)


@router.delete("/sessions/{session_id}", response_model=MessageResponse)
async def discard_session(
    session_id: UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Discard an in-progress attempt — deletes the session and every rating in it, so the next visit starts fresh."""
    session = await _get_owned_session(db, session_id, user)
    if session.status != AssessmentSessionStatus.in_progress:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Only an in-progress session can be discarded")
    await db.delete(session)
    await db.commit()
    return MessageResponse(message="Assessment progress discarded.")


@router.post("/sessions/{session_id}/complete", response_model=AssessmentSessionResponse)
async def complete_session(
    session_id: UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Mark a session finished. Scoring/reporting happen in a later pass."""
    session = await _get_owned_session(db, session_id, user)
    session.status = AssessmentSessionStatus.completed
    session.completed_at = datetime.now(timezone.utc)
    await db.commit()
    await db.refresh(session)
    return AssessmentSessionResponse.model_validate(session)
