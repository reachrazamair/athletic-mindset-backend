"""
ADMIN ASSESSMENT ROUTER — full CRUD over the question bank.

This is the whole point of not hardcoding questions: every phase, factor,
dimension, question, option, and sport-category mapping here is a normal
database row that admins add/edit/delete through the CMS. Nothing about the
assessment's content lives in application code.
"""

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.assessment_content_sync import delete_question_content, sync_question_content
from app.database import get_db
from app.dependencies import require_role
from app.models import (
    AssessmentDimension,
    AssessmentFactor,
    AssessmentPhase,
    AssessmentQuestion,
    AssessmentQuestionOption,
    QuestionTierEnum,
    QuestionTypeEnum,
    MeasurementTypeEnum,
    User,
)
from app.schemas import (
    DimensionCreate,
    DimensionNode,
    DimensionResponse,
    DimensionUpdate,
    FactorCreate,
    FactorNode,
    FactorResponse,
    FactorUpdate,
    MessageResponse,
    PhaseCreate,
    PhaseNode,
    PhaseResponse,
    PhaseUpdate,
    QuestionAdminResponse,
    QuestionCreate,
    QuestionOptionResponse,
    QuestionReorderRequest,
    QuestionUpdate,
    TaxonomyResponse,
)

router = APIRouter(prefix="/admin/assessment", tags=["admin-assessment"])


# --- Taxonomy: phases / factors / dimensions ---

@router.get("/taxonomy", response_model=TaxonomyResponse)
async def get_taxonomy(
    _: User = Depends(require_role("admin")),
    db: AsyncSession = Depends(get_db),
):
    """Full phase -> factor -> dimension tree, for admin pickers and the grouped question list."""
    result = await db.execute(
        select(AssessmentPhase)
        .options(selectinload(AssessmentPhase.factors).selectinload(AssessmentFactor.dimensions))
        .order_by(AssessmentPhase.order)
    )
    phases = result.scalars().unique().all()
    return TaxonomyResponse(
        phases=[
            PhaseNode(
                id=p.id, key=p.key, name=p.name, order=p.order,
                factors=[
                    FactorNode(
                        id=f.id, phase_id=f.phase_id, key=f.key, name=f.name, order=f.order,
                        dimensions=[
                            DimensionNode(id=d.id, factor_id=d.factor_id, key=d.key, name=d.name, order=d.order)
                            for d in sorted(f.dimensions, key=lambda d: d.order)
                        ],
                    )
                    for f in sorted(p.factors, key=lambda f: f.order)
                ],
            )
            for p in phases
        ]
    )


@router.post("/phases", response_model=PhaseResponse, status_code=status.HTTP_201_CREATED)
async def create_phase(
    body: PhaseCreate,
    _: User = Depends(require_role("admin")),
    db: AsyncSession = Depends(get_db),
):
    phase = AssessmentPhase(**body.model_dump())
    db.add(phase)
    await db.commit()
    await db.refresh(phase)
    return PhaseResponse.model_validate(phase)


@router.patch("/phases/{phase_id}", response_model=PhaseResponse)
async def update_phase(
    phase_id: UUID,
    body: PhaseUpdate,
    _: User = Depends(require_role("admin")),
    db: AsyncSession = Depends(get_db),
):
    phase = await db.get(AssessmentPhase, phase_id)
    if phase is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Phase not found")
    for field, value in body.model_dump(exclude_unset=True).items():
        setattr(phase, field, value)
    await db.commit()
    await db.refresh(phase)
    return PhaseResponse.model_validate(phase)


@router.delete("/phases/{phase_id}", response_model=MessageResponse)
async def delete_phase(
    phase_id: UUID,
    _: User = Depends(require_role("admin")),
    db: AsyncSession = Depends(get_db),
):
    phase = await db.get(AssessmentPhase, phase_id)
    if phase is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Phase not found")
    await db.delete(phase)
    await db.commit()
    return MessageResponse(message="Phase deleted.")


@router.post("/factors", response_model=FactorResponse, status_code=status.HTTP_201_CREATED)
async def create_factor(
    body: FactorCreate,
    _: User = Depends(require_role("admin")),
    db: AsyncSession = Depends(get_db),
):
    factor = AssessmentFactor(**body.model_dump())
    db.add(factor)
    await db.commit()
    await db.refresh(factor)
    return FactorResponse.model_validate(factor)


@router.patch("/factors/{factor_id}", response_model=FactorResponse)
async def update_factor(
    factor_id: UUID,
    body: FactorUpdate,
    _: User = Depends(require_role("admin")),
    db: AsyncSession = Depends(get_db),
):
    factor = await db.get(AssessmentFactor, factor_id)
    if factor is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Factor not found")
    for field, value in body.model_dump(exclude_unset=True).items():
        setattr(factor, field, value)
    await db.commit()
    await db.refresh(factor)
    return FactorResponse.model_validate(factor)


@router.delete("/factors/{factor_id}", response_model=MessageResponse)
async def delete_factor(
    factor_id: UUID,
    _: User = Depends(require_role("admin")),
    db: AsyncSession = Depends(get_db),
):
    factor = await db.get(AssessmentFactor, factor_id)
    if factor is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Factor not found")
    await db.delete(factor)
    await db.commit()
    return MessageResponse(message="Factor deleted.")


@router.post("/dimensions", response_model=DimensionResponse, status_code=status.HTTP_201_CREATED)
async def create_dimension(
    body: DimensionCreate,
    _: User = Depends(require_role("admin")),
    db: AsyncSession = Depends(get_db),
):
    dimension = AssessmentDimension(**body.model_dump())
    db.add(dimension)
    await db.commit()
    await db.refresh(dimension)
    return DimensionResponse.model_validate(dimension)


@router.patch("/dimensions/{dimension_id}", response_model=DimensionResponse)
async def update_dimension(
    dimension_id: UUID,
    body: DimensionUpdate,
    _: User = Depends(require_role("admin")),
    db: AsyncSession = Depends(get_db),
):
    dimension = await db.get(AssessmentDimension, dimension_id)
    if dimension is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Dimension not found")
    for field, value in body.model_dump(exclude_unset=True).items():
        setattr(dimension, field, value)
    await db.commit()
    await db.refresh(dimension)
    return DimensionResponse.model_validate(dimension)


@router.delete("/dimensions/{dimension_id}", response_model=MessageResponse)
async def delete_dimension(
    dimension_id: UUID,
    _: User = Depends(require_role("admin")),
    db: AsyncSession = Depends(get_db),
):
    dimension = await db.get(AssessmentDimension, dimension_id)
    if dimension is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Dimension not found")
    await db.delete(dimension)
    await db.commit()
    return MessageResponse(message="Dimension deleted.")


# --- Questions ---

def _to_admin_response(question: AssessmentQuestion) -> QuestionAdminResponse:
    dimension = question.dimension
    factor = dimension.factor
    phase = factor.phase
    return QuestionAdminResponse(
        id=question.id,
        dimension_id=question.dimension_id,
        phase_name=phase.name,
        factor_name=factor.name,
        dimension_name=dimension.name,
        order=question.order,
        prompt=question.prompt,
        helper_text=question.helper_text,
        question_type=question.question_type.value,
        measurement_type=question.measurement_type.value,
        tier=question.tier.value,
        reverse_scored=question.reverse_scored,
        sport_category_overrides=question.sport_category_overrides,
        position_overrides=question.position_overrides,
        is_active=question.is_active,
        options=[QuestionOptionResponse.model_validate(o) for o in sorted(question.options, key=lambda o: o.order)],
    )


async def _get_question_with_relations(db: AsyncSession, question_id: UUID) -> AssessmentQuestion | None:
    result = await db.execute(
        select(AssessmentQuestion)
        .where(AssessmentQuestion.id == question_id)
        .options(
            selectinload(AssessmentQuestion.options),
            selectinload(AssessmentQuestion.dimension).selectinload(AssessmentDimension.factor).selectinload(AssessmentFactor.phase),
        )
    )
    return result.scalar_one_or_none()


@router.get("/questions", response_model=list[QuestionAdminResponse])
async def list_questions(
    _: User = Depends(require_role("admin")),
    db: AsyncSession = Depends(get_db),
):
    """All questions (active and inactive), with options and taxonomy names, for the admin list."""
    result = await db.execute(
        select(AssessmentQuestion)
        .options(
            selectinload(AssessmentQuestion.options),
            selectinload(AssessmentQuestion.dimension).selectinload(AssessmentDimension.factor).selectinload(AssessmentFactor.phase),
        )
        .order_by(AssessmentQuestion.order)
    )
    questions = result.scalars().unique().all()
    return [_to_admin_response(q) for q in questions]


@router.post("/questions", response_model=QuestionAdminResponse, status_code=status.HTTP_201_CREATED)
async def create_question(
    body: QuestionCreate,
    _: User = Depends(require_role("admin")),
    db: AsyncSession = Depends(get_db),
):
    data = body.model_dump(exclude={"options", "question_type", "measurement_type", "tier"})
    question = AssessmentQuestion(
        **data,
        question_type=QuestionTypeEnum(body.question_type),
        measurement_type=MeasurementTypeEnum(body.measurement_type),
        tier=QuestionTierEnum(body.tier),
    )
    db.add(question)
    await db.flush()

    for opt in body.options:
        db.add(AssessmentQuestionOption(question_id=question.id, **opt.model_dump()))
    await db.flush()

    question_with_content = await _get_question_with_relations(db, question.id)
    await sync_question_content(db, question_with_content)
    await db.commit()

    created = await _get_question_with_relations(db, question.id)
    return _to_admin_response(created)


@router.patch("/questions/{question_id}", response_model=QuestionAdminResponse)
async def update_question(
    question_id: UUID,
    body: QuestionUpdate,
    _: User = Depends(require_role("admin")),
    db: AsyncSession = Depends(get_db),
):
    question = await _get_question_with_relations(db, question_id)
    if question is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Question not found")

    data = body.model_dump(exclude_unset=True, exclude={"options", "question_type", "measurement_type", "tier"})
    for field, value in data.items():
        setattr(question, field, value)
    if body.question_type is not None:
        question.question_type = QuestionTypeEnum(body.question_type)
    if body.measurement_type is not None:
        question.measurement_type = MeasurementTypeEnum(body.measurement_type)
    if body.tier is not None:
        question.tier = QuestionTierEnum(body.tier)

    if body.options is not None:
        # Options are replaced wholesale — the editor always submits the full set.
        for opt in list(question.options):
            await db.delete(opt)
        await db.flush()
        for opt in body.options:
            db.add(AssessmentQuestionOption(question_id=question.id, **opt.model_dump()))
        await db.flush()

    question_with_content = await _get_question_with_relations(db, question_id)
    await sync_question_content(db, question_with_content)
    await db.commit()

    updated = await _get_question_with_relations(db, question_id)
    return _to_admin_response(updated)


@router.delete("/questions/{question_id}", response_model=MessageResponse)
async def delete_question(
    question_id: UUID,
    _: User = Depends(require_role("admin")),
    db: AsyncSession = Depends(get_db),
):
    question = await db.get(AssessmentQuestion, question_id)
    if question is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Question not found")
    await delete_question_content(db, question_id)
    await db.delete(question)
    await db.commit()
    return MessageResponse(message="Question deleted.")


@router.patch("/questions/reorder", response_model=MessageResponse)
async def reorder_questions(
    body: QuestionReorderRequest,
    _: User = Depends(require_role("admin")),
    db: AsyncSession = Depends(get_db),
):
    for item in body.items:
        question = await db.get(AssessmentQuestion, item.id)
        if question is not None:
            question.order = item.order
    await db.commit()
    return MessageResponse(message="Order updated.")
