"""
MODELS — Database tables as Python classes.

Each class here = one table in PostgreSQL.
SQLAlchemy reads these and creates the actual tables via Alembic migrations.
"""

import enum
import uuid
from datetime import date, datetime

from sqlalchemy import Boolean, Date, DateTime, Enum, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func

from app.database import Base


class RoleEnum(str, enum.Enum):
    athlete = "athlete"
    parent = "parent"
    coach = "coach"
    admin = "admin"


class SportCategoryEnum(str, enum.Enum):
    """
    Team / Individual / Combat — chosen directly by the athlete as part of the
    assessment's registration step (see AM Assessment Framework v1, Section 1).
    Drives which adaptive question text an assessment shows.
    """
    team = "team"
    individual = "individual"
    combat = "combat"


class User(Base):
    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True, nullable=False)
    hashed_password: Mapped[str] = mapped_column(String(255), nullable=False)
    first_name: Mapped[str | None] = mapped_column(String(100), nullable=True)
    last_name: Mapped[str | None] = mapped_column(String(100), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    is_verified: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    # Relationships
    roles: Mapped[list["UserRole"]] = relationship("UserRole", back_populates="user", lazy="selectin")
    athlete_profile: Mapped["AthleteProfile | None"] = relationship(
        "AthleteProfile", back_populates="user", uselist=False, lazy="selectin", cascade="all, delete-orphan"
    )
    subscription: Mapped["Subscription | None"] = relationship(
        "Subscription", back_populates="user", uselist=False, lazy="selectin", cascade="all, delete-orphan"
    )


class AthleteProfile(Base):
    """
    Demographic + sport info captured during onboarding.

    One-to-one with a user. Nullable fields so a partially completed profile is
    still valid — we treat the profile as "complete" when the core fields
    (sport, level) are filled.
    """

    __tablename__ = "athlete_profiles"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), unique=True, nullable=False
    )

    birth_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    sex: Mapped[str | None] = mapped_column(String(50), nullable=True)
    ethnicity: Mapped[str | None] = mapped_column(String(100), nullable=True)
    primary_sport: Mapped[str | None] = mapped_column(String(100), nullable=True)
    competition_level: Mapped[str | None] = mapped_column(String(100), nullable=True)
    position: Mapped[str | None] = mapped_column(String(100), nullable=True)
    # Team / Individual / Combat — set during the assessment's registration step.
    sport_category: Mapped[SportCategoryEnum | None] = mapped_column(Enum(SportCategoryEnum), nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    user: Mapped["User"] = relationship("User", back_populates="athlete_profile")


class SubscriptionStatus(str, enum.Enum):
    """Mirrors Stripe's own subscription status values (see Stripe docs)."""
    incomplete = "incomplete"
    trialing = "trialing"
    active = "active"
    past_due = "past_due"
    canceled = "canceled"
    unpaid = "unpaid"


class SubscriptionPlan(str, enum.Enum):
    """Which pricing-page tier this subscription is for (see landing/Pricing.tsx). Team is sales-assisted, never created here."""
    free = "free"
    elite = "elite"
    team = "team"


class Subscription(Base):
    """
    One row per user tracking their plan — the single source of truth for
    whether the assessment is unlocked. The free plan is granted directly
    (see POST /billing/subscribe-free); paid plans are kept in sync via
    Stripe webhooks (see app/routers/billing.py). Nothing here is admin-edited.
    """

    __tablename__ = "subscriptions"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), unique=True, nullable=False
    )
    plan: Mapped[SubscriptionPlan] = mapped_column(Enum(SubscriptionPlan), nullable=False, default=SubscriptionPlan.free)
    # Which specific PricingPlan row this is (e.g. main's Elite vs. parents'
    # Elite — same `plan` enum value, different audience/price). Null for
    # free grants, which aren't audience-specific in a way that matters here.
    pricing_plan_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("pricing_plans.id"), nullable=True
    )
    # Null for a free plan granted before Stripe keys were configured — every
    # paid plan has one, created lazily on first checkout.
    stripe_customer_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    stripe_subscription_id: Mapped[str | None] = mapped_column(String(255), unique=True, nullable=True)
    status: Mapped[SubscriptionStatus] = mapped_column(
        Enum(SubscriptionStatus), nullable=False, default=SubscriptionStatus.incomplete
    )
    current_period_end: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    cancel_at_period_end: Mapped[bool] = mapped_column(Boolean, default=False)

    # Set when an admin price change is sent to existing subscribers (see
    # PATCH /admin/pricing/plans/{id}/price, notify_existing_subscribers=true).
    # cancel_at_period_end is flipped on at the same time — that's the safe
    # "no response" default (access lapses at period end, no auto-charge at
    # the new amount). Acknowledging swaps the subscription to the new price
    # for the next cycle and clears both; declining just clears this flag,
    # since the cancellation is already in effect.
    pending_price_notice: Mapped[bool] = mapped_column(Boolean, default=False)
    pending_monthly_amount_cents: Mapped[int | None] = mapped_column(Integer, nullable=True)
    pending_yearly_amount_cents: Mapped[int | None] = mapped_column(Integer, nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    user: Mapped["User"] = relationship("User", back_populates="subscription")


class ContentEntry(Base):
    """
    One piece of editable site text, in one language.

    Every string Admin can edit lives here as (key, locale) → value. For example
    key "home.hero.title" has one row for "en" and one for "es". English is the
    master; other languages are auto-translated from it and can be re-saved.
    """

    __tablename__ = "content_entries"
    __table_args__ = (UniqueConstraint("key", "locale", name="uq_content_key_locale"),)

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    key: Mapped[str] = mapped_column(String(255), index=True, nullable=False)
    locale: Mapped[str] = mapped_column(String(10), index=True, nullable=False)
    value: Mapped[str] = mapped_column(Text, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class UserRole(Base):
    __tablename__ = "user_roles"
    __table_args__ = (UniqueConstraint("user_id", "role", name="uq_user_role"),)

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    role: Mapped[RoleEnum] = mapped_column(Enum(RoleEnum), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    # Relationships
    user: Mapped["User"] = relationship("User", back_populates="roles")


# --- Assessment ---


class QuestionTypeEnum(str, enum.Enum):
    likert = "likert"
    scenario = "scenario"


class MeasurementTypeEnum(str, enum.Enum):
    trait = "trait"
    state = "state"


class QuestionTierEnum(str, enum.Enum):
    free = "free"
    elite = "elite"


class ResponseModeEnum(str, enum.Enum):
    """How the athlete answers a question."""
    single_select = "single_select"  # pick the one option that fits best
    rate_all = "rate_all"  # rate every option's effectiveness (situational judgment / SJT format)


class AssessmentSessionStatus(str, enum.Enum):
    in_progress = "in_progress"
    completed = "completed"


class AssessmentPhase(Base):
    """Top-level grouping: Preparation, Competition, Teamwork."""

    __tablename__ = "assessment_phases"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    key: Mapped[str] = mapped_column(String(50), unique=True, nullable=False)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    factors: Mapped[list["AssessmentFactor"]] = relationship(
        "AssessmentFactor", back_populates="phase", order_by="AssessmentFactor.order",
        cascade="all, delete-orphan",
    )


class AssessmentFactor(Base):
    """Mid-level grouping within a phase, e.g. Grit, Coachability, Drive."""

    __tablename__ = "assessment_factors"
    __table_args__ = (UniqueConstraint("phase_id", "key", name="uq_factor_phase_key"),)

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    phase_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("assessment_phases.id", ondelete="CASCADE"), nullable=False
    )
    key: Mapped[str] = mapped_column(String(50), nullable=False)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    phase: Mapped["AssessmentPhase"] = relationship("AssessmentPhase", back_populates="factors")
    dimensions: Mapped[list["AssessmentDimension"]] = relationship(
        "AssessmentDimension", back_populates="factor", order_by="AssessmentDimension.order",
        cascade="all, delete-orphan",
    )


class AssessmentDimension(Base):
    """Granular measure within a factor, e.g. Persistence, Intrinsic Motivation."""

    __tablename__ = "assessment_dimensions"
    __table_args__ = (UniqueConstraint("factor_id", "key", name="uq_dimension_factor_key"),)

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    factor_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("assessment_factors.id", ondelete="CASCADE"), nullable=False
    )
    key: Mapped[str] = mapped_column(String(50), nullable=False)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    factor: Mapped["AssessmentFactor"] = relationship("AssessmentFactor", back_populates="dimensions")
    questions: Mapped[list["AssessmentQuestion"]] = relationship(
        "AssessmentQuestion", back_populates="dimension", order_by="AssessmentQuestion.order",
    )


class AssessmentQuestion(Base):
    """
    One question in the bank. `prompt` is the universal/default wording; the
    JSON override fields hold sport-category- and position-specific variants
    that the resolver swaps in based on the athlete's profile. Everything here
    is admin-editable — nothing about a question is hardcoded in application
    code beyond the resolution order (position > sport category > default).
    """

    __tablename__ = "assessment_questions"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    dimension_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("assessment_dimensions.id", ondelete="CASCADE"), nullable=False
    )
    order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    prompt: Mapped[str] = mapped_column(Text, nullable=False)
    helper_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    question_type: Mapped[QuestionTypeEnum] = mapped_column(Enum(QuestionTypeEnum), nullable=False)
    measurement_type: Mapped[MeasurementTypeEnum] = mapped_column(Enum(MeasurementTypeEnum), nullable=False)
    tier: Mapped[QuestionTierEnum] = mapped_column(Enum(QuestionTierEnum), nullable=False, default=QuestionTierEnum.free)
    response_mode: Mapped[ResponseModeEnum] = mapped_column(
        Enum(ResponseModeEnum), nullable=False, default=ResponseModeEnum.single_select
    )
    reverse_scored: Mapped[bool] = mapped_column(Boolean, default=False)
    # {"individual": "...", "combat": "..."} — category key -> replacement prompt text
    sport_category_overrides: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    # {"QB": "...", "Goalie": "..."} — position name -> replacement prompt text
    position_overrides: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    dimension: Mapped["AssessmentDimension"] = relationship("AssessmentDimension", back_populates="questions")
    options: Mapped[list["AssessmentQuestionOption"]] = relationship(
        "AssessmentQuestionOption", back_populates="question", order_by="AssessmentQuestionOption.order",
        cascade="all, delete-orphan",
    )


class AssessmentQuestionOption(Base):
    """One lettered answer choice (A-E) for a question."""

    __tablename__ = "assessment_question_options"
    __table_args__ = (UniqueConstraint("question_id", "label", name="uq_option_question_label"),)

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    question_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("assessment_questions.id", ondelete="CASCADE"), nullable=False
    )
    label: Mapped[str] = mapped_column(String(1), nullable=False)
    text: Mapped[str] = mapped_column(Text, nullable=False)
    score: Mapped[int] = mapped_column(Integer, nullable=False)
    tag: Mapped[str | None] = mapped_column(String(100), nullable=True)
    order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    question: Mapped["AssessmentQuestion"] = relationship("AssessmentQuestion", back_populates="options")


class AssessmentSession(Base):
    """One athlete's attempt at the assessment (a tier's worth of questions)."""

    __tablename__ = "assessment_sessions"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    tier: Mapped[QuestionTierEnum] = mapped_column(Enum(QuestionTierEnum), nullable=False)
    status: Mapped[AssessmentSessionStatus] = mapped_column(
        Enum(AssessmentSessionStatus), nullable=False, default=AssessmentSessionStatus.in_progress
    )
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    responses: Mapped[list["AssessmentResponse"]] = relationship(
        "AssessmentResponse", back_populates="session", cascade="all, delete-orphan",
    )


class AssessmentResponse(Base):
    """
    One rated option within a session. Raw storage only — no scoring.

    For a "rate every option" question, the athlete produces one row per
    option (this row's `rating`, 1-5, is their effectiveness rating for that
    specific option). For a "single select" question, one row exists for the
    chosen option and `rating` is left null.
    """

    __tablename__ = "assessment_responses"
    __table_args__ = (
        UniqueConstraint("session_id", "question_id", "option_id", name="uq_response_session_question_option"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    session_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("assessment_sessions.id", ondelete="CASCADE"), nullable=False
    )
    question_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("assessment_questions.id", ondelete="CASCADE"), nullable=False
    )
    option_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("assessment_question_options.id", ondelete="CASCADE"), nullable=False
    )
    rating: Mapped[int | None] = mapped_column(Integer, nullable=True)
    answered_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    session: Mapped["AssessmentSession"] = relationship("AssessmentSession", back_populates="responses")


# --- Pricing ---


class PricingPlan(Base):
    """
    One pricing card. `audience` scopes it to whichever page shows it — the
    main pricing page ("main": home #pricing + /pricing, with real checkout
    wiring keyed off `key` — free = granted directly, elite = real Stripe
    checkout, team = links to /contact) or one of the marketing pages that
    show their own tailored pricing copy ("athletes", "parents", "coaches").
    `key` is only unique per audience, not globally.

    Only "main" plans ever carry real Stripe pricing — the audience-specific
    pages are pure marketing copy (`cta_href` is a plain link, never wired to
    checkout), so their price label fields are always plain editable text.

    The price label fields are plain display text — for a plan with a real
    Stripe price (currently only main's Elite), they're auto-generated from
    monthly_amount_cents/yearly_amount_cents whenever those change (see
    PATCH /admin/pricing/plans/{id}/price), which also mints a new Stripe
    Price and points checkout at it.
    """

    __tablename__ = "pricing_plans"
    __table_args__ = (UniqueConstraint("audience", "key", name="uq_pricing_plan_audience_key"),)

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    audience: Mapped[str] = mapped_column(String(20), nullable=False, default="main")
    key: Mapped[str] = mapped_column(String(50), nullable=False)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    monthly_price_label: Mapped[str] = mapped_column(String(50), nullable=False)  # e.g. "$10.42", "$0", "Custom"
    monthly_period_label: Mapped[str] = mapped_column(String(50), nullable=False, default="")  # e.g. "/mo", "forever"
    yearly_price_label: Mapped[str] = mapped_column(String(50), nullable=False)
    yearly_period_label: Mapped[str] = mapped_column(String(50), nullable=False, default="")
    # Small note under the price, shown only in the monthly view (e.g. Elite's "Billed as $125/year").
    note: Mapped[str | None] = mapped_column(String(255), nullable=True)
    features: Mapped[list[str]] = mapped_column(JSONB, nullable=False, default=list)
    # Shown as locked/greyed-out bullets below the regular features (Free tier only, today).
    locked_features: Mapped[list[str]] = mapped_column(JSONB, nullable=False, default=list)
    cta_label: Mapped[str] = mapped_column(String(100), nullable=False)
    # Plain link target — only meaningful (and only rendered as a link rather
    # than a functional checkout button) for non-"main" audiences.
    cta_href: Mapped[str | None] = mapped_column(String(255), nullable=True)
    featured: Mapped[bool] = mapped_column(Boolean, default=False)
    order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

    # Real Stripe pricing — only ever set for "main" audience plans with an
    # actual charge (Elite). Null for everything else.
    stripe_product_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    monthly_amount_cents: Mapped[int | None] = mapped_column(Integer, nullable=True)
    yearly_amount_cents: Mapped[int | None] = mapped_column(Integer, nullable=True)
    stripe_price_id_monthly: Mapped[str | None] = mapped_column(String(255), nullable=True)
    stripe_price_id_yearly: Mapped[str | None] = mapped_column(String(255), nullable=True)
    currency: Mapped[str] = mapped_column(String(10), nullable=False, default="usd")

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
