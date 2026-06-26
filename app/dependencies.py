"""
DEPENDENCIES — Reusable FastAPI dependencies for route protection.

Use these in route handlers to require authentication or specific roles.

Example:
    @router.get("/dashboard")
    async def dashboard(user: User = Depends(get_current_user)):
        ...

    @router.get("/admin/users")
    async def admin_users(user: User = Depends(require_role("admin"))):
        ...
"""

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import decode_access_token
from app.database import get_db
from app.models import User

# Extracts the Bearer token from the Authorization header
security = HTTPBearer()


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: AsyncSession = Depends(get_db),
) -> User:
    """
    Validates the JWT token and returns the user.
    Raises 401 if token is invalid or user not found.
    """
    payload = decode_access_token(credentials.credentials)
    if payload is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid or expired token")

    user_id = payload.get("sub")
    if user_id is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token payload")

    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()

    if user is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found")

    if not user.is_active:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Account deactivated")

    return user


def require_role(role: str):
    """
    Returns a dependency that checks if the current user has the required role.

    Usage: Depends(require_role("admin"))
    """

    async def role_checker(user: User = Depends(get_current_user)) -> User:
        user_roles = [r.role.value for r in user.roles]
        if role not in user_roles:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=f"Requires role: {role}")
        return user

    return role_checker
