"""User, profile, and admin-user schemas."""

from __future__ import annotations

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

UserRole = Literal["athlete", "admin", "super_admin"]


class AuthProviderResponse(BaseModel):
    """Enabled OAuth provider descriptor."""

    provider: Literal["google", "microsoft", "dev"]
    label: str
    enabled: bool
    login_url: str


class AuthProvidersResponse(BaseModel):
    """Configured OAuth providers."""

    providers: list[AuthProviderResponse]


class OAuthLoginResponse(BaseModel):
    """OAuth provider authorization URL."""

    authorization_url: str


class UserResponse(BaseModel):
    """Current/user-management user response."""

    id: UUID
    organization_id: UUID
    email: str
    name: str
    role: UserRole
    sport_team: str | None = None
    profile_complete: bool
    is_active: bool
    created_at: datetime | None = None

    model_config = ConfigDict(from_attributes=True)


class SessionResponse(BaseModel):
    """Authenticated session payload."""

    user: UserResponse
    next_route: str


class UpdateProfileRequest(BaseModel):
    """Athlete profile completion request."""

    name: str = Field(min_length=1, max_length=255)
    sport_team: str = Field(min_length=1, max_length=255)
    selected_role: Literal["athlete"] = "athlete"


class UpdateProfileResponse(UserResponse):
    """Profile update response with frontend route hint."""

    next_route: str = "/chat"


class UpdateUserRoleRequest(BaseModel):
    """Super-admin role update request."""

    role: UserRole


class LogoutResponse(BaseModel):
    """Logout status response."""

    status: Literal["ok"] = "ok"
