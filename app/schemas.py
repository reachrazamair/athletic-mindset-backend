"""
SCHEMAS — Request/response shapes for the API.

These define what data the frontend sends and what it gets back.
Pydantic validates everything automatically — bad data gets rejected before hitting the DB.
"""

import uuid
from datetime import date, datetime

from pydantic import BaseModel, EmailStr, Field


# --- Auth ---

class RegisterRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)
    first_name: str | None = Field(default=None, max_length=100)
    last_name: str | None = Field(default=None, max_length=100)


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class SetRoleRequest(BaseModel):
    role: str = Field(pattern="^(athlete|parent|coach)$")


class ForgotPasswordRequest(BaseModel):
    email: EmailStr


class ResetPasswordRequest(BaseModel):
    token: str
    new_password: str = Field(min_length=8, max_length=128)


class VerifyEmailRequest(BaseModel):
    token: str


class UpdateProfileRequest(BaseModel):
    first_name: str = Field(min_length=1, max_length=100)
    last_name: str = Field(min_length=1, max_length=100)


class ChangePasswordRequest(BaseModel):
    current_password: str
    new_password: str = Field(min_length=8, max_length=128)


class MessageResponse(BaseModel):
    message: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: "UserResponse"


# --- User ---

class RoleResponse(BaseModel):
    role: str
    created_at: datetime

    class Config:
        from_attributes = True


class UserResponse(BaseModel):
    id: uuid.UUID
    email: str
    first_name: str | None
    last_name: str | None
    is_active: bool
    is_verified: bool
    roles: list[RoleResponse]
    athlete_profile: "AthleteProfileResponse | None" = None
    created_at: datetime

    class Config:
        from_attributes = True


# --- Athlete Profile (onboarding demographics) ---

class AthleteProfileUpdate(BaseModel):
    birth_date: date | None = None
    sex: str | None = Field(default=None, max_length=50)
    ethnicity: str | None = Field(default=None, max_length=100)
    primary_sport: str | None = Field(default=None, max_length=100)
    competition_level: str | None = Field(default=None, max_length=100)
    position: str | None = Field(default=None, max_length=100)
    sport_category: str | None = Field(default=None, pattern="^(team|individual|combat)$")


class AthleteProfileResponse(BaseModel):
    birth_date: date | None
    sex: str | None
    ethnicity: str | None
    primary_sport: str | None
    competition_level: str | None
    position: str | None
    sport_category: str | None

    class Config:
        from_attributes = True


# --- Account Deletion ---

class DeactivateAccountRequest(BaseModel):
    password: str


# --- Admin ---

class CreateAdminRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)
    first_name: str | None = None
    last_name: str | None = None


# --- Content (CMS) ---

class ContentItem(BaseModel):
    """One editable string, keyed by name. Value is always the English (master)."""
    key: str = Field(min_length=1, max_length=255)
    value: str


class SaveContentRequest(BaseModel):
    """Save one or more English strings. Other languages are auto-translated."""
    items: list[ContentItem] = Field(min_length=1)


class ContentEntryResponse(BaseModel):
    key: str
    locale: str
    value: str

    class Config:
        from_attributes = True


class SaveContentResponse(BaseModel):
    saved: int
    locales: list[str]
    translated: bool


# --- Assessment: taxonomy (admin) ---

class PhaseCreate(BaseModel):
    key: str = Field(min_length=1, max_length=50)
    name: str = Field(min_length=1, max_length=100)
    order: int = 0


class PhaseUpdate(BaseModel):
    key: str | None = Field(default=None, min_length=1, max_length=50)
    name: str | None = Field(default=None, min_length=1, max_length=100)
    order: int | None = None


class PhaseResponse(BaseModel):
    id: uuid.UUID
    key: str
    name: str
    order: int

    class Config:
        from_attributes = True


class FactorCreate(BaseModel):
    phase_id: uuid.UUID
    key: str = Field(min_length=1, max_length=50)
    name: str = Field(min_length=1, max_length=100)
    order: int = 0


class FactorUpdate(BaseModel):
    phase_id: uuid.UUID | None = None
    key: str | None = Field(default=None, min_length=1, max_length=50)
    name: str | None = Field(default=None, min_length=1, max_length=100)
    order: int | None = None


class FactorResponse(BaseModel):
    id: uuid.UUID
    phase_id: uuid.UUID
    key: str
    name: str
    order: int

    class Config:
        from_attributes = True


class DimensionCreate(BaseModel):
    factor_id: uuid.UUID
    key: str = Field(min_length=1, max_length=50)
    name: str = Field(min_length=1, max_length=100)
    order: int = 0


class DimensionUpdate(BaseModel):
    factor_id: uuid.UUID | None = None
    key: str | None = Field(default=None, min_length=1, max_length=50)
    name: str | None = Field(default=None, min_length=1, max_length=100)
    order: int | None = None


class DimensionResponse(BaseModel):
    id: uuid.UUID
    factor_id: uuid.UUID
    key: str
    name: str
    order: int

    class Config:
        from_attributes = True


class DimensionNode(DimensionResponse):
    pass


class FactorNode(FactorResponse):
    dimensions: list[DimensionNode] = []


class PhaseNode(PhaseResponse):
    factors: list[FactorNode] = []


class TaxonomyResponse(BaseModel):
    """Full phase -> factor -> dimension tree, for admin pickers."""
    phases: list[PhaseNode]


# --- Assessment: questions (admin) ---

class QuestionOptionInput(BaseModel):
    label: str = Field(min_length=1, max_length=1)
    text: str = Field(min_length=1)
    score: int = Field(ge=1, le=5)
    tag: str | None = Field(default=None, max_length=100)
    order: int = 0


class QuestionOptionResponse(BaseModel):
    id: uuid.UUID
    label: str
    text: str
    score: int
    tag: str | None
    order: int

    class Config:
        from_attributes = True


class QuestionCreate(BaseModel):
    dimension_id: uuid.UUID
    order: int = 0
    prompt: str = Field(min_length=1)
    helper_text: str | None = None
    question_type: str = Field(pattern="^(likert|scenario)$")
    measurement_type: str = Field(pattern="^(trait|state)$")
    tier: str = Field(pattern="^(free|elite)$")
    response_mode: str = Field(default="single_select", pattern="^(single_select|rate_all)$")
    reverse_scored: bool = False
    sport_category_overrides: dict[str, str] | None = None
    position_overrides: dict[str, str] | None = None
    is_active: bool = True
    options: list[QuestionOptionInput] = Field(min_length=2, max_length=6)


class QuestionUpdate(BaseModel):
    dimension_id: uuid.UUID | None = None
    order: int | None = None
    prompt: str | None = Field(default=None, min_length=1)
    helper_text: str | None = None
    question_type: str | None = Field(default=None, pattern="^(likert|scenario)$")
    measurement_type: str | None = Field(default=None, pattern="^(trait|state)$")
    tier: str | None = Field(default=None, pattern="^(free|elite)$")
    response_mode: str | None = Field(default=None, pattern="^(single_select|rate_all)$")
    reverse_scored: bool | None = None
    sport_category_overrides: dict[str, str] | None = None
    position_overrides: dict[str, str] | None = None
    is_active: bool | None = None
    options: list[QuestionOptionInput] | None = Field(default=None, min_length=2, max_length=6)


class QuestionAdminResponse(BaseModel):
    id: uuid.UUID
    dimension_id: uuid.UUID
    phase_name: str
    factor_name: str
    dimension_name: str
    order: int
    prompt: str
    helper_text: str | None
    question_type: str
    measurement_type: str
    tier: str
    response_mode: str
    reverse_scored: bool
    sport_category_overrides: dict[str, str] | None
    position_overrides: dict[str, str] | None
    is_active: bool
    options: list[QuestionOptionResponse]


class QuestionReorderItem(BaseModel):
    id: uuid.UUID
    order: int


class QuestionReorderRequest(BaseModel):
    items: list[QuestionReorderItem] = Field(min_length=1)


# --- Assessment: athlete-facing ---

class ResolvedOptionResponse(BaseModel):
    """An answer choice as shown to the athlete — no score or tag leaked."""
    id: uuid.UUID
    label: str
    text: str


class ResolvedQuestionResponse(BaseModel):
    """A question with its text already resolved for the athlete's profile."""
    id: uuid.UUID
    order: int
    prompt: str
    helper_text: str | None
    question_type: str
    measurement_type: str
    response_mode: str
    options: list[ResolvedOptionResponse]


class AssessmentSessionRequest(BaseModel):
    tier: str = Field(pattern="^(free|elite)$")


class AssessmentSessionResponse(BaseModel):
    id: uuid.UUID
    tier: str
    status: str
    started_at: datetime
    completed_at: datetime | None

    class Config:
        from_attributes = True


class AssessmentSessionRatingRequest(BaseModel):
    """One question's full set of option ratings (rate-all format): option_id -> 1-5 rating."""
    question_id: uuid.UUID
    ratings: dict[uuid.UUID, int] = Field(min_length=1)


class AssessmentSessionCurrentResponse(BaseModel):
    session: AssessmentSessionResponse | None
    # question_id -> { option_id -> rating }
    ratings: dict[uuid.UUID, dict[uuid.UUID, int]]


# --- Billing (Stripe) ---

class CheckoutSessionResponse(BaseModel):
    checkout_url: str


class PortalSessionResponse(BaseModel):
    portal_url: str


class BillingStatusResponse(BaseModel):
    has_access: bool
    plan: str | None
    status: str | None
    current_period_end: datetime | None
    cancel_at_period_end: bool
    # Set when an admin price change was sent to existing subscribers and this
    # user hasn't responded yet — the frontend shows the notice popup while true.
    pending_price_notice: bool
    pending_monthly_amount_cents: int | None
    pending_yearly_amount_cents: int | None


class CheckoutSessionRequest(BaseModel):
    billing_period: str = Field(default="monthly", pattern="^(monthly|yearly)$")


# --- Pricing plans ---
# Text fields (name/description/features/price labels/...) are edited through
# the normal CMS Content editor via ContentEntry — no admin CRUD schemas
# needed for that. Only the real Stripe-backed amount gets a dedicated
# endpoint, since minting a new Stripe Price is a side effect a plain content
# save can't do.

class PricingPlanAdminResponse(BaseModel):
    id: uuid.UUID
    key: str
    name: str
    description: str
    monthly_price_label: str
    monthly_period_label: str
    yearly_price_label: str
    yearly_period_label: str
    note: str | None
    features: list[str]
    locked_features: list[str]
    cta_label: str
    featured: bool
    order: int
    is_active: bool
    stripe_product_id: str | None
    monthly_amount_cents: int | None
    yearly_amount_cents: int | None
    currency: str

    class Config:
        from_attributes = True


class PlanPriceUpdateRequest(BaseModel):
    monthly_amount_cents: int = Field(ge=0)
    yearly_amount_cents: int = Field(ge=0)
    # If true, every currently-active subscriber on this plan is immediately
    # set to cancel_at_period_end (the safe default) and shown an in-app
    # notice to acknowledge (move to the new price next cycle) or decline
    # (let the already-scheduled cancellation stand). If false (default),
    # this only affects checkout for new customers going forward.
    notify_existing_subscribers: bool = False


class ResolvedPricingPlanResponse(BaseModel):
    """Public, translated shape — no id-keyed content-sync internals leaked to the frontend."""
    key: str
    name: str
    description: str
    monthly_price_label: str
    monthly_period_label: str
    yearly_price_label: str
    yearly_period_label: str
    note: str | None
    features: list[str]
    locked_features: list[str]
    cta_label: str
    featured: bool
