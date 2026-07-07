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


class AthleteProfileResponse(BaseModel):
    birth_date: date | None
    sex: str | None
    ethnicity: str | None
    primary_sport: str | None
    competition_level: str | None
    position: str | None

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
