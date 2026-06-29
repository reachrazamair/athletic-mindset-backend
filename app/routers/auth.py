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

from app.auth import create_access_token, hash_password, verify_password
from app.database import get_db
from app.dependencies import get_current_user
from app.models import RoleEnum, User, UserRole
from app.schemas import LoginRequest, RegisterRequest, SetRoleRequest, TokenResponse, UserResponse

router = APIRouter(prefix="/auth", tags=["auth"])


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
