"""Authentication dependencies.

Decodes the app JWT from either the Authorization: Bearer header (priority) or
an ``access_token`` HttpOnly cookie (set by an SSO flow), then returns the
authenticated principal. This scaffold uses a lightweight JWT-decode approach
(``pyjwt``); swap in fastapi-users' ``current_user`` once a real user model and
UserManager exist (see the comment block below).
"""
from typing import Annotated

import jwt
import structlog
from fastapi import Cookie, Depends, HTTPException, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel

from app.core.config import settings

logger = structlog.get_logger(__name__)

_bearer = HTTPBearer(auto_error=False)


class AuthPrincipal(BaseModel):
    """Minimal authenticated principal decoded from the JWT.

    Replace with your User ORM model once fastapi-users is wired up. The
    ``sub`` claim carries the user id.
    """

    sub: str
    claims: dict


async def _resolve_token_from_request(
    request: Request,
    bearer: HTTPAuthorizationCredentials | None = Depends(_bearer),
    access_token: str | None = Cookie(default=None),
) -> str | None:
    """Extract the JWT from the Bearer header (priority) or access_token cookie."""
    if bearer and bearer.credentials:
        return bearer.credentials
    if access_token:
        return access_token
    return None


def _decode_token(token: str | None) -> AuthPrincipal | None:
    """Decode and validate the app JWT, returning the principal or None."""
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
    return AuthPrincipal(sub=str(sub), claims=payload)


async def current_active_user(
    token: Annotated[str | None, Depends(_resolve_token_from_request)],
) -> AuthPrincipal:
    """Get the currently authenticated principal.

    Accepts a JWT from the Authorization: Bearer header OR the access_token
    HttpOnly cookie. Raises HTTP 401 if not authenticated.

    NOTE: For a real app, replace this with fastapi-users:

        from app.auth.users import fastapi_users
        current_active_user = fastapi_users.current_user(active=True)

    and fetch the User row from the DB inside the dependency.
    """
    principal = _decode_token(token)
    if principal is None:
        raise HTTPException(status_code=401, detail="Not authenticated")
    return principal


async def optional_current_user(
    token: Annotated[str | None, Depends(_resolve_token_from_request)],
) -> AuthPrincipal | None:
    """Get the current principal if authenticated, else None."""
    return _decode_token(token)
