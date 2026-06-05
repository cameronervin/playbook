"""Super-admin user-management routes."""

from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Query

from app.api.v1.dependencies import SuperAdminUserDep, UserAdminServiceDep
from app.schemas.users import UpdateUserRoleRequest, UserResponse

router = APIRouter(prefix="/admin/users", tags=["Admin Users"])


@router.get("", response_model=list[UserResponse])
async def list_users(
    actor: SuperAdminUserDep,
    service: UserAdminServiceDep,
    role: str | None = None,
    limit: Annotated[int, Query(ge=1, le=500)] = 100,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> list[UserResponse]:
    """List organization users."""
    return await service.list_users(
        actor=actor,
        role=role,
        limit=limit,
        offset=offset,
    )


@router.patch("/{user_id}/role", response_model=UserResponse)
async def update_role(
    user_id: UUID,
    request: UpdateUserRoleRequest,
    actor: SuperAdminUserDep,
    service: UserAdminServiceDep,
) -> UserResponse:
    """Update an organization user's role."""
    return await service.update_role(actor=actor, user_id=user_id, request=request)
