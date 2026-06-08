"""Audit log service."""

from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.audit import AuditLog
from app.models.identity import User
from app.repositories.audit import AuditLogRepository
from app.schemas.audit import AuditLogResponse


def audit_log_to_response(audit_log: AuditLog) -> AuditLogResponse:
    """Map an AuditLog ORM object to a public DTO."""
    return AuditLogResponse(
        id=audit_log.id,
        organization_id=audit_log.organization_id,
        actor_user_id=audit_log.actor_user_id,
        action=audit_log.action,
        target_type=audit_log.target_type,
        target_id=audit_log.target_id,
        metadata=audit_log.audit_metadata,
        created_at=audit_log.created_at,
    )


class AuditLogService:
    """Orchestrates immutable audit event creation and querying."""

    def __init__(
        self,
        session: AsyncSession,
        *,
        audit_repo: AuditLogRepository | None = None,
    ) -> None:
        self.session = session
        self.audit_repo = audit_repo or AuditLogRepository(session)

    async def record(
        self,
        *,
        actor: User | None,
        organization_id: UUID,
        action: str,
        target_type: str,
        target_id: UUID | None,
        metadata: dict[str, Any],
    ) -> AuditLog:
        """Append an audit event without committing."""
        return await self.audit_repo.create(
            organization_id=organization_id,
            actor_user_id=actor.id if actor else None,
            action=action,
            target_type=target_type,
            target_id=target_id,
            metadata=metadata,
        )

    async def list_for_super_admin(
        self,
        *,
        actor: User,
        actor_user_id: UUID | None = None,
        action: str | None = None,
        target_type: str | None = None,
        target_id: UUID | None = None,
        start_at: datetime | None = None,
        end_at: datetime | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> list[AuditLogResponse]:
        """Return org-scoped audit logs for a super admin."""
        rows = await self.audit_repo.list_by_organization(
            actor.organization_id,
            actor_user_id=actor_user_id,
            action=action,
            target_type=target_type,
            target_id=target_id,
            start_at=start_at,
            end_at=end_at,
            limit=limit,
            offset=offset,
        )
        return [audit_log_to_response(row) for row in rows]
