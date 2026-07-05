"""Application session token and cookie helpers."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import UUID

import jwt
from fastapi import Response

from app.core.config import Settings
from app.models.identity import User


def create_access_token(
    user: User,
    settings: Settings,
    *,
    session_id: UUID,
    expires_at: datetime | None = None,
) -> str:
    """Create the app JWT used by Playbook API dependencies."""
    now = datetime.now(UTC)
    resolved_expires_at = expires_at or now + timedelta(seconds=settings.JWT_LIFETIME_SECONDS)
    payload = {
        "sub": str(user.id),
        "sid": str(session_id),
        "role": user.role,
        "iat": int(now.timestamp()),
        "exp": int(resolved_expires_at.timestamp()),
    }
    return jwt.encode(payload, settings.SECRET_KEY, algorithm="HS256")


def cookie_domain(settings: Settings) -> str | None:
    """Return the configured cookie domain, normalized for FastAPI cookies."""
    return settings.COOKIE_DOMAIN or None


def set_access_token_cookie(
    response: Response,
    token: str,
    settings: Settings,
) -> None:
    """Attach the app access token as an HttpOnly cookie."""
    response.set_cookie(
        settings.ACCESS_TOKEN_COOKIE_NAME,
        token,
        max_age=settings.JWT_LIFETIME_SECONDS,
        httponly=True,
        secure=settings.ENVIRONMENT.lower() in {"prod", "production"},
        samesite="lax",
        domain=cookie_domain(settings),
    )


def clear_access_token_cookie(response: Response, settings: Settings) -> None:
    """Clear the configured app access token cookie."""
    response.delete_cookie(
        settings.ACCESS_TOKEN_COOKIE_NAME,
        domain=cookie_domain(settings),
    )


def clear_oauth_state_cookie(response: Response, settings: Settings) -> None:
    """Clear the OAuth CSRF state cookie."""
    response.delete_cookie(
        settings.OAUTH_STATE_COOKIE_NAME,
        domain=cookie_domain(settings),
    )
