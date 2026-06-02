"""Service-to-service authentication dependency for KB API endpoints.

The calling app authenticates to KB using a shared Bearer token
(``settings.KB_API_SECRET``). All /api/kb/* routes are protected — the health
endpoint at /health is intentionally excluded.

Usage:
    from app.api.deps.service_auth import verify_service_auth
    router = APIRouter(dependencies=[Depends(verify_service_auth)])
"""
from __future__ import annotations

import secrets

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.core.config import settings

_bearer = HTTPBearer(auto_error=False)


async def verify_service_auth(
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer),
) -> None:
    """Reject requests that don't supply the correct KB_API_SECRET Bearer token.

    Uses constant-time comparison to prevent timing-oracle attacks.
    """
    if credentials is None or not secrets.compare_digest(
        credentials.credentials.encode(),
        settings.KB_API_SECRET.encode(),
    ):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or missing service credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )
