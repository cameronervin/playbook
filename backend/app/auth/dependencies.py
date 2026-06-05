"""Authentication and role dependencies."""
from typing import Annotated
from uuid import UUID

import jwt
import structlog
from fastapi import Cookie, Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.infrastructure.db.session import get_db
from app.models.identity import User
from app.repositories.identity import UserRepository

logger = structlog.get_logger(__name__)

_bearer = HTTPBearer(auto_error=False)

AUTH_COOKIE_NAME = "access_token"


async def _resolve_token_from_request(
    request: Request,
    bearer: HTTPAuthorizationCredentials | None = Depends(_bearer),
    access_token: str | None = Cookie(default=None, alias=AUTH_COOKIE_NAME),
) -> str | None:
    """Extract the JWT from the Bearer header (priority) or access_token cookie."""
    if bearer and bearer.credentials:
        return bearer.credentials
    if access_token:
        return access_token
    return None


def _decode_user_id(token: str | None) -> UUID | None:
    """Decode and validate the app JWT, returning the subject UUID or None."""
    if not token:
        return None
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=["HS256"])
    except jwt.ExpiredSignatureError:
        return None
    except jwt.PyJWTError:
        return None

    sub = payload.get("sub")
    if not sub:
        return None
    try:
        return UUID(str(sub))
    except ValueError:
        return None


async def current_active_user(
    token: Annotated[str | None, Depends(_resolve_token_from_request)],
    session: Annotated[AsyncSession, Depends(get_db)],
) -> User:
    """Return the active Playbook user represented by the app session token."""
    user_id = _decode_user_id(token)
    if user_id is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
        )

    user = await UserRepository(session).get(user_id)
    if user is None or not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
        )
    structlog.contextvars.bind_contextvars(user_id=str(user.id), role=user.role)
    return user


get_current_user = current_active_user


async def optional_current_user(
    token: Annotated[str | None, Depends(_resolve_token_from_request)],
    session: Annotated[AsyncSession, Depends(get_db)],
) -> User | None:
    """Get the current active user if authenticated, else None."""
    user_id = _decode_user_id(token)
    if user_id is None:
        return None
    user = await UserRepository(session).get(user_id)
    if user is None or not user.is_active:
        return None
    structlog.contextvars.bind_contextvars(user_id=str(user.id), role=user.role)
    return user


def is_profile_complete(user: User) -> bool:
    """Whether the user has the MVP-required profile fields."""
    if user.role != "athlete":
        return True
    return bool(user.name and user.email and user.sport_team)


def require_athlete(user: Annotated[User, Depends(current_active_user)]) -> User:
    """Require the current user to be an athlete."""
    if user.role != "athlete":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Athlete role required",
        )
    return user


def require_admin(user: Annotated[User, Depends(current_active_user)]) -> User:
    """Require an admin-capable user."""
    if user.role not in {"admin", "super_admin"}:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin role required",
        )
    return user


def require_super_admin(user: Annotated[User, Depends(current_active_user)]) -> User:
    """Require a super-admin user."""
    if user.role != "super_admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Super admin role required",
        )
    return user
