"""Authentication API routes."""

from __future__ import annotations

from fastapi import APIRouter, Request, Response, status
from fastapi.responses import RedirectResponse

from app.api.v1.dependencies import AuthServiceDep, CurrentUserDep, RateLimitServiceDep
from app.auth.dev_personas import DevAuthPersona
from app.schemas.users import (
    AuthProvidersResponse,
    LogoutResponse,
    OAuthLoginResponse,
    SessionResponse,
)
from app.services.auth_service import ProviderName
from app.services.rate_limit import RateLimitPolicy

router = APIRouter(prefix="/auth", tags=["Authentication"])


def _prefers_html(request: Request) -> bool:
    """Return whether the caller looks like a browser navigation."""
    accept = request.headers.get("accept", "")
    return "text/html" in accept and "application/json" not in accept


@router.get("/providers", response_model=AuthProvidersResponse)
async def providers(
    service: AuthServiceDep,
) -> AuthProvidersResponse:
    """List configured OAuth providers."""
    return service.providers()


@router.get("/{provider}/login", response_model=OAuthLoginResponse)
async def login(
    provider: ProviderName,
    request: Request,
    response: Response,
    service: AuthServiceDep,
    rate_limiter: RateLimitServiceDep,
    persona: DevAuthPersona | None = None,
) -> OAuthLoginResponse:
    """Return an OAuth authorization URL."""
    await rate_limiter.enforce(RateLimitPolicy.AUTH, request=request)
    return await service.login_url(
        provider=provider,
        request=request,
        response=response,
        persona=persona,
    )


@router.get("/{provider}/callback", response_model=SessionResponse)
async def callback(
    provider: ProviderName,
    code: str,
    state: str,
    request: Request,
    response: Response,
    service: AuthServiceDep,
    rate_limiter: RateLimitServiceDep,
) -> SessionResponse | RedirectResponse:
    """Complete OAuth login and create an app session."""
    await rate_limiter.enforce(RateLimitPolicy.AUTH, request=request)
    session = await service.callback(
        provider=provider,
        code=code,
        state=state,
        request=request,
        response=response,
    )
    if _prefers_html(request):
        return service.browser_redirect_response(session)
    return session.public_response()


@router.post("/logout", response_model=LogoutResponse)
async def logout(
    request: Request,
    response: Response,
    service: AuthServiceDep,
) -> LogoutResponse:
    """Clear the app session cookie."""
    await service.logout(request, response)
    return LogoutResponse()


@router.post("/session/refresh", status_code=status.HTTP_204_NO_CONTENT)
async def refresh_session(
    _user: CurrentUserDep,
) -> Response:
    """Refresh the current app session on authenticated user activity."""
    return Response(status_code=status.HTTP_204_NO_CONTENT)
