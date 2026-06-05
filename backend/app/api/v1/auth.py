"""Authentication API routes."""

from __future__ import annotations

from fastapi import APIRouter, Request, Response

from app.api.v1.dependencies import AuthServiceDep
from app.schemas.users import (
    AuthProvidersResponse,
    LogoutResponse,
    OAuthLoginResponse,
    SessionResponse,
)
from app.services.auth_service import ProviderName

router = APIRouter(prefix="/auth", tags=["Authentication"])


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
) -> OAuthLoginResponse:
    """Return an OAuth authorization URL."""
    return await service.login_url(provider=provider, request=request, response=response)


@router.get("/{provider}/callback", response_model=SessionResponse)
async def callback(
    provider: ProviderName,
    code: str,
    state: str,
    request: Request,
    response: Response,
    service: AuthServiceDep,
) -> SessionResponse:
    """Complete OAuth login and create an app session."""
    return await service.callback(
        provider=provider,
        code=code,
        state=state,
        request=request,
        response=response,
    )


@router.post("/logout", response_model=LogoutResponse)
async def logout(
    response: Response,
    service: AuthServiceDep,
) -> LogoutResponse:
    """Clear the app session cookie."""
    service.logout(response)
    return LogoutResponse()
