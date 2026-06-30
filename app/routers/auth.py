"""
AUTH ROUTER:

POST /auth/register  → create account (no role yet)
POST /auth/login     → get JWT token
POST /auth/set-role  → assign a role to the logged-in user
GET  /auth/me        → get current user info
"""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import (
    create_access_token,
    create_purpose_token,
    decode_purpose_token,
    hash_password,
    verify_password,
)
from app.config import settings
from app.database import get_db
from app.dependencies import get_current_user
from app.email import render_email, send_email
from app.models import RoleEnum, User, UserRole
from app.schemas import (
    ForgotPasswordRequest,
    LoginRequest,
    MessageResponse,
    RegisterRequest,
    ResetPasswordRequest,
    SetRoleRequest,
    TokenResponse,
    UserResponse,
)

router = APIRouter(prefix="/auth", tags=["auth"])

# How long password-reset links stay valid
RESET_TOKEN_EXPIRE_MINUTES = 30


@router.post("/register", response_model=TokenResponse, status_code=status.HTTP_201_CREATED)
async def register(body: RegisterRequest, db: AsyncSession = Depends(get_db)):
    """Create a new account. Returns a token so the user is immediately logged in."""

    # Check if email already exists
    result = await db.execute(select(User).where(User.email == body.email))
    if result.scalar_one_or_none():
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Email already registered")

    # Create user
    user = User(
        email=body.email,
        hashed_password=hash_password(body.password),
        first_name=body.first_name,
        last_name=body.last_name,
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)

    # Generate token (no roles yet)
    token = create_access_token(str(user.id), [])

    return TokenResponse(access_token=token, user=UserResponse.model_validate(user))


@router.post("/login", response_model=TokenResponse)
async def login(body: LoginRequest, db: AsyncSession = Depends(get_db)):
    """Authenticate with email + password. Returns a JWT token."""

    result = await db.execute(select(User).where(User.email == body.email))
    user = result.scalar_one_or_none()

    if not user or not verify_password(body.password, user.hashed_password):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid email or password")

    if not user.is_active:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Account deactivated")

    # Build roles list for token
    roles = [r.role.value for r in user.roles]
    token = create_access_token(str(user.id), roles)

    return TokenResponse(access_token=token, user=UserResponse.model_validate(user))


@router.post("/forgot-password", response_model=MessageResponse)
async def forgot_password(body: ForgotPasswordRequest, db: AsyncSession = Depends(get_db)):
    """
    Start a password reset. Always returns the same message whether or not the
    email exists — this avoids leaking which emails are registered.
    """
    result = await db.execute(select(User).where(User.email == body.email))
    user = result.scalar_one_or_none()

    # Only send an email if the account actually exists.
    if user and user.is_active:
        token = create_purpose_token(str(user.id), "password_reset", RESET_TOKEN_EXPIRE_MINUTES)
        reset_link = f"{settings.FRONTEND_URL}/reset-password?token={token}"
        html = render_email(
            heading="Reset your password",
            body_html=(
                "We received a request to reset your Athletic Mindset password. "
                f"Choose a new one using the button below. This link expires in "
                f"{RESET_TOKEN_EXPIRE_MINUTES} minutes."
            ),
            button_label="Reset Password",
            button_url=reset_link,
        )
        await send_email(user.email, "Reset your password", html)

    return MessageResponse(message="If an account exists for that email, a reset link is on its way.")


@router.post("/reset-password", response_model=MessageResponse)
async def reset_password(body: ResetPasswordRequest, db: AsyncSession = Depends(get_db)):
    """Set a new password using the token from the reset email."""
    user_id = decode_purpose_token(body.token, "password_reset")
    if user_id is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="This reset link is invalid or has expired. Please request a new one.",
        )

    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="This reset link is invalid or has expired. Please request a new one.",
        )

    user.hashed_password = hash_password(body.new_password)
    await db.commit()

    return MessageResponse(message="Your password has been reset. You can now sign in.")


@router.post("/set-role", response_model=UserResponse)
async def set_role(
    body: SetRoleRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Assign a role to the current user. Called after signup during role selection."""

    # Check if user already has this role
    existing_roles = [r.role.value for r in user.roles]
    if body.role in existing_roles:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Role already assigned")

    # Add role
    user_role = UserRole(user_id=user.id, role=RoleEnum(body.role))
    db.add(user_role)
    await db.commit()
    await db.refresh(user)

    return UserResponse.model_validate(user)


@router.get("/me", response_model=UserResponse)
async def get_me(user: User = Depends(get_current_user)):
    """Get the current authenticated user's info and roles."""
    return UserResponse.model_validate(user)
