"""Authentication and role dependencies."""
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Annotated
from uuid import UUID

import jwt
import structlog
from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.session import create_access_token
from app.core.config import Settings, get_request_settings
from app.core.exceptions import UnauthorizedError
from app.infrastructure.db.session import get_db
from app.models.identity import User
from app.repositories.identity import AppSessionRepository, UserRepository

logger = structlog.get_logger(__name__)

_bearer = HTTPBearer(auto_error=False)

_SESSION_EXPIRED_REASON = "session_expired"
_SESSION_INVALID_REASON = "session_invalid"


@dataclass(frozen=True)
class SessionTokenPayload:
    """Validated app-session JWT claims."""

    user_id: UUID
    session_id: UUID
    expires_at: datetime


async def _resolve_token_from_request(
    request: Request,
    bearer: HTTPAuthorizationCredentials | None = Depends(_bearer),
) -> str | None:
    """Extract the JWT from the Bearer header (priority) or configured cookie."""
    if bearer and bearer.credentials:
        return bearer.credentials
    settings = get_request_settings(request)
    if access_token := request.cookies.get(settings.ACCESS_TOKEN_COOKIE_NAME):
        return access_token
    return None


def _mark_cookie_clear(request: Request) -> None:
    request.state.clear_access_token_cookie = True


def _mark_cookie_refresh(request: Request, token: str) -> None:
    request.state.refreshed_access_token = token


def _unauthorized(reason: str) -> UnauthorizedError:
    return UnauthorizedError("Not authenticated", details={"reason": reason})


def _decode_session_token(
    token: str | None,
    settings: Settings,
    request: Request,
) -> SessionTokenPayload:
    """Decode and validate the app JWT and required server-session claims."""
    if not token:
        raise _unauthorized(_SESSION_INVALID_REASON)
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=["HS256"])
    except jwt.ExpiredSignatureError:
        _mark_cookie_clear(request)
        raise _unauthorized(_SESSION_EXPIRED_REASON) from None
    except jwt.PyJWTError:
        _mark_cookie_clear(request)
        raise _unauthorized(_SESSION_INVALID_REASON) from None

    sub = payload.get("sub")
    sid = payload.get("sid")
    exp = payload.get("exp")
    if not sub or not sid or not exp:
        _mark_cookie_clear(request)
        raise _unauthorized(_SESSION_INVALID_REASON)
    try:
        return SessionTokenPayload(
            user_id=UUID(str(sub)),
            session_id=UUID(str(sid)),
            expires_at=datetime.fromtimestamp(int(exp), tz=UTC),
        )
    except (TypeError, ValueError):
        _mark_cookie_clear(request)
        raise _unauthorized(_SESSION_INVALID_REASON) from None


async def current_active_user(
    token: Annotated[str | None, Depends(_resolve_token_from_request)],
    session: Annotated[AsyncSession, Depends(get_db)],
    settings: Annotated[Settings, Depends(get_request_settings)],
    request: Request,
) -> User:
    """Return the active Playbook user represented by the app session token."""
    token_payload = _decode_session_token(token, settings, request)
    app_session = await AppSessionRepository(session).get(token_payload.session_id)
    now = datetime.now(UTC)
    if app_session is None or app_session.user_id != token_payload.user_id:
        _mark_cookie_clear(request)
        raise _unauthorized(_SESSION_INVALID_REASON)
    if app_session.revoked_at is not None:
        _mark_cookie_clear(request)
        raise _unauthorized("session_revoked")
    if app_session.expires_at <= now:
        _mark_cookie_clear(request)
        raise _unauthorized(_SESSION_EXPIRED_REASON)

    user = await UserRepository(session).get(token_payload.user_id)
    if user is None or not user.is_active:
        _mark_cookie_clear(request)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
        )

    expires_at: datetime | None = None
    if token_payload.expires_at <= now + timedelta(seconds=settings.JWT_REFRESH_THRESHOLD_SECONDS):
        expires_at = now + timedelta(seconds=settings.JWT_LIFETIME_SECONDS)
        refreshed_token = create_access_token(
            user,
            settings,
            session_id=app_session.id,
            expires_at=expires_at,
        )
        _mark_cookie_refresh(request, refreshed_token)
    await AppSessionRepository(session).touch(
        app_session,
        last_seen_at=now,
        expires_at=expires_at,
    )
    await session.commit()
    structlog.contextvars.bind_contextvars(user_id=str(user.id), role=user.role)
    return user


get_current_user = current_active_user


async def optional_current_user(
    token: Annotated[str | None, Depends(_resolve_token_from_request)],
    session: Annotated[AsyncSession, Depends(get_db)],
    settings: Annotated[Settings, Depends(get_request_settings)],
    request: Request,
) -> User | None:
    """Get the current active user if authenticated, else None."""
    try:
        token_payload = _decode_session_token(token, settings, request)
    except UnauthorizedError:
        return None
    app_session = await AppSessionRepository(session).get(token_payload.session_id)
    now = datetime.now(UTC)
    if (
        app_session is None
        or app_session.user_id != token_payload.user_id
        or app_session.revoked_at is not None
        or app_session.expires_at <= now
    ):
        _mark_cookie_clear(request)
        return None
    user = await UserRepository(session).get(token_payload.user_id)
    if user is None or not user.is_active:
        _mark_cookie_clear(request)
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
