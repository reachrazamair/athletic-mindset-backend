"""
ASSESSMENT ROUTER — athlete-facing: take the assessment, one question at a time.

GET  /assessment/questions          → active questions for a tier, text resolved for the caller
POST /assessment/sessions           → start (or resume) a session for a tier
GET  /assessment/sessions/current   → the caller's current session + answers so far, for resume
PUT  /assessment/sessions/{id}/answers    → upsert one answer
POST /assessment/sessions/{id}/complete   → mark a session finished

No scoring happens here — responses are stored as-is for a later reporting pass.
"""

from datetime import datetime, timezone
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.assessment_resolver import resolve_question_variant
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
    AssessmentSessionAnswerRequest,
    AssessmentSessionCurrentResponse,
    AssessmentSessionRequest,
    AssessmentSessionResponse,
    ResolvedOptionResponse,
    ResolvedQuestionResponse,
)

router = APIRouter(prefix="/assessment", tags=["assessment"])


@router.get("/questions", response_model=list[ResolvedQuestionResponse])
async def list_questions(
    tier: str = "free",
    lang: str = "en",
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Active questions for a tier, with prompt text resolved for the caller's sport/position and translated to the requested language."""
    result = await db.execute(
        select(AssessmentQuestion)
        .options(selectinload(AssessmentQuestion.options))
        .where(AssessmentQuestion.is_active.is_(True), AssessmentQuestion.tier == QuestionTierEnum(tier))
        .order_by(AssessmentQuestion.order)
    )
    questions = result.scalars().all()
    profile = user.athlete_profile

    # Question/option text is admin-authored content, translated the same way
    # as the rest of the site's copy: an English master ContentEntry row per
    # key, auto-translated into any language on first request. Keys look like
    #   assessment.questions.{question_id}.prompt
    #   assessment.questions.{question_id}.sport_category_overrides.{category}
    #   assessment.questions.{question_id}.position_overrides.{position}
    #   assessment.questions.{question_id}.options.{option_id}.text
    # (admin_assessment.py keeps these rows in sync whenever a question is saved).
    translations = await _build_locale_map(db, lang)

    def _t(key: str, fallback: str) -> str:
        return translations.get(key, fallback)

    resolved: list[ResolvedQuestionResponse] = []
    for q in questions:
        key_suffix, fallback_prompt = resolve_question_variant(q, profile)
        resolved.append(
            ResolvedQuestionResponse(
                id=q.id,
                order=q.order,
                prompt=_t(f"assessment.questions.{q.id}.{key_suffix}", fallback_prompt),
                helper_text=_t(
                    f"assessment.questions.{q.id}.helper_text",
                    q.helper_text or "",
                ) or None,
                question_type=q.question_type.value,
                measurement_type=q.measurement_type.value,
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
    user: User = Depends(get_current_user),
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
    """The caller's most recent session for a tier (in-progress or completed) plus its answers."""
    result = await db.execute(
        select(AssessmentSession)
        .where(AssessmentSession.user_id == user.id, AssessmentSession.tier == QuestionTierEnum(tier))
        .order_by(AssessmentSession.started_at.desc())
    )
    session = result.scalars().first()

    if session is None:
        return AssessmentSessionCurrentResponse(session=None, answers={})

    responses_result = await db.execute(
        select(AssessmentResponse).where(AssessmentResponse.session_id == session.id)
    )
    answers = {r.question_id: r.option_id for r in responses_result.scalars().all()}

    return AssessmentSessionCurrentResponse(
        session=AssessmentSessionResponse.model_validate(session),
        answers=answers,
    )


async def _get_owned_session(db: AsyncSession, session_id: UUID, user: User) -> AssessmentSession:
    result = await db.execute(select(AssessmentSession).where(AssessmentSession.id == session_id))
    session = result.scalar_one_or_none()
    if session is None or session.user_id != user.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Session not found")
    return session


@router.put("/sessions/{session_id}/answers", response_model=AssessmentSessionResponse)
async def submit_answer(
    session_id: UUID,
    body: AssessmentSessionAnswerRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Upsert the caller's answer to one question within their session."""
    session = await _get_owned_session(db, session_id, user)
    if session.status != AssessmentSessionStatus.in_progress:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="This session is already completed")

    result = await db.execute(
        select(AssessmentResponse).where(
            AssessmentResponse.session_id == session.id,
            AssessmentResponse.question_id == body.question_id,
        )
    )
    response = result.scalar_one_or_none()

    if response is None:
        db.add(AssessmentResponse(session_id=session.id, question_id=body.question_id, option_id=body.option_id))
    else:
        response.option_id = body.option_id

    await db.commit()
    await db.refresh(session)
    return AssessmentSessionResponse.model_validate(session)


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
