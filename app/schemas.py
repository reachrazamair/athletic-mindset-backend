"""
SCHEMAS — Request/response shapes for the API.

These define what data the frontend sends and what it gets back.
Pydantic validates everything automatically — bad data gets rejected before hitting the DB.
"""

import uuid
from datetime import datetime

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
    created_at: datetime

    class Config:
        from_attributes = True


# --- Admin ---

class CreateAdminRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)
    first_name: str | None = None
    last_name: str | None = None
