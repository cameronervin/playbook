"""Current-user profile routes."""

from __future__ import annotations

from fastapi import APIRouter

from app.api.v1.dependencies import (
    AthleteUserDep,
    CurrentUserDep,
    UserProfileServiceDep,
)
from app.schemas.users import UpdateProfileRequest, UpdateProfileResponse, UserResponse

router = APIRouter(prefix="/users", tags=["Users"])


@router.get("/me", response_model=UserResponse)
async def me(
    user: CurrentUserDep,
    service: UserProfileServiceDep,
) -> UserResponse:
    """Return current authenticated user."""
    return await service.current_user(user)


@router.patch("/me/profile", response_model=UpdateProfileResponse)
async def update_profile(
    request: UpdateProfileRequest,
    user: AthleteUserDep,
    service: UserProfileServiceDep,
) -> UpdateProfileResponse:
    """Complete/update current athlete profile."""
    return await service.update_profile(user=user, request=request)
