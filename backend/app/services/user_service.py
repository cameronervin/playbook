"""User profile and admin role services."""

from __future__ import annotations

from uuid import UUID

import structlog
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import NotFoundError, ValidationError
from app.models.identity import User
from app.repositories.identity import UserRepository
from app.schemas.users import (
    UpdateProfileRequest,
    UpdateProfileResponse,
    UpdateUserRoleRequest,
    UserResponse,
)
from app.services.audit_service import AuditLogService
from app.services.auth_service import user_to_response

logger = structlog.get_logger(__name__)

_ALLOWED_ROLES = {"athlete", "admin", "super_admin"}


class UserProfileService:
    """Current-user profile operations."""

    def __init__(
        self,
        session: AsyncSession,
        *,
        user_repo: UserRepository | None = None,
    ) -> None:
        self.session = session
        self.user_repo = user_repo or UserRepository(session)

    async def current_user(self, user: User) -> UserResponse:
        """Return the authenticated user profile."""
        return user_to_response(user)

    async def update_profile(
        self,
        *,
        user: User,
        request: UpdateProfileRequest,
    ) -> UpdateProfileResponse:
        """Complete/update the athlete profile and commit."""
        if user.role != "athlete" or request.selected_role != "athlete":
            raise ValidationError("Only athlete profile completion is supported")
        updated = await self.user_repo.update_profile(
            user,
            name=request.name.strip(),
            sport_team=request.sport_team.strip(),
        )
        await self.session.commit()
        public = user_to_response(updated)
        logger.info("user_profile_updated", user_id=str(updated.id))
        return UpdateProfileResponse(**public.model_dump(), next_route="/chat")


class UserAdminService:
    """Super-admin user and role-management operations."""

    def __init__(
        self,
        session: AsyncSession,
        *,
        user_repo: UserRepository | None = None,
        audit_service: AuditLogService | None = None,
    ) -> None:
        self.session = session
        self.user_repo = user_repo or UserRepository(session)
        self.audit_service = audit_service or AuditLogService(session)

    async def list_users(
        self,
        *,
        actor: User,
        limit: int = 100,
        offset: int = 0,
        role: str | None = None,
    ) -> list[UserResponse]:
        """List organization users for super-admin role management."""
        if role is not None and role not in _ALLOWED_ROLES:
            raise ValidationError("Invalid user role filter", details={"role": role})
        users = await self.user_repo.list_by_organization(
            actor.organization_id,
            role=role,
            limit=limit,
            offset=offset,
        )
        return [user_to_response(user) for user in users]

    async def update_role(
        self,
        *,
        actor: User,
        user_id: UUID,
        request: UpdateUserRoleRequest,
    ) -> UserResponse:
        """Update a user's role and audit the change atomically."""
        if request.role not in _ALLOWED_ROLES:
            raise ValidationError("Invalid user role", details={"role": request.role})
        target = await self.user_repo.get(user_id)
        if target is None or target.organization_id != actor.organization_id:
            raise NotFoundError("User", str(user_id))

        previous_role = target.role
        updated = await self.user_repo.update_role(target, role=request.role)
        await self.audit_service.record(
            actor=actor,
            organization_id=actor.organization_id,
            action="user.role_changed",
            target_type="user",
            target_id=updated.id,
            metadata={"previous_role": previous_role, "new_role": updated.role},
        )
        await self.session.commit()
        logger.info(
            "user_role_changed",
            actor_user_id=str(actor.id),
            target_user_id=str(updated.id),
            previous_role=previous_role,
            new_role=updated.role,
        )
        return user_to_response(updated)
