"""Local-development auth bootstrap routes."""

from __future__ import annotations

import structlog
from fastapi import APIRouter
from fastapi.responses import RedirectResponse

from app.api.v1.dependencies import DevAuthServiceDep, SettingsDep
from app.services.auth_service import set_access_token_cookie
from app.services.dev_auth_service import DevAuthPersona

logger = structlog.get_logger(__name__)

router = APIRouter(prefix="/dev", tags=["Development"])


@router.get("/session/{persona}", response_class=RedirectResponse, status_code=303)
async def bootstrap_session(
    persona: DevAuthPersona,
    service: DevAuthServiceDep,
    settings: SettingsDep,
) -> RedirectResponse:
    """Create a local-development session and redirect to the frontend."""
    principal = await service.create_session(persona)
    redirect = RedirectResponse(
        url=f"{settings.FRONTEND_URL.rstrip('/')}{principal.next_route}",
        status_code=303,
    )
    set_access_token_cookie(redirect, principal.token, settings)
    logger.info(
        "dev_auth_session_bootstrapped",
        persona=persona,
        user_id=str(principal.user_id),
        organization_id=str(principal.organization_id),
    )
    return redirect
