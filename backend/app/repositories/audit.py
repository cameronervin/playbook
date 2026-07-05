"""Repositories for immutable audit log data."""

from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

from fastapi import Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.infrastructure.db.session import get_db
from app.models.audit import AuditLog


class AuditLogRepository:
    """Append-only data access for privileged action audit events."""

    def __init__(self, session: AsyncSession = Depends(get_db)) -> None:
        self.session = session

    async def create(
        self,
        *,
        organization_id: UUID,
        actor_user_id: UUID | None,
        action: str,
        target_type: str,
        target_id: UUID | None,
        metadata: dict[str, Any],
    ) -> AuditLog:
        """Create an audit event without committing the transaction."""
        audit_log = AuditLog(
            organization_id=organization_id,
            actor_user_id=actor_user_id,
            action=action,
            target_type=target_type,
            target_id=target_id,
            audit_metadata=metadata,
        )
        self.session.add(audit_log)
        await self.session.flush()
        await self.session.refresh(audit_log)
        return audit_log

    async def list_by_organization(
        self,
        organization_id: UUID,
        *,
        actor_user_id: UUID | None = None,
        action: str | None = None,
        target_type: str | None = None,
        target_id: UUID | None = None,
        start_at: datetime | None = None,
        end_at: datetime | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> list[AuditLog]:
        """Return filtered audit events for super-admin review."""
        stmt = select(AuditLog).where(AuditLog.organization_id == organization_id)
        if actor_user_id is not None:
            stmt = stmt.where(AuditLog.actor_user_id == actor_user_id)
        if action is not None:
            stmt = stmt.where(AuditLog.action == action)
        if target_type is not None:
            stmt = stmt.where(AuditLog.target_type == target_type)
        if target_id is not None:
            stmt = stmt.where(AuditLog.target_id == target_id)
        if start_at is not None:
            stmt = stmt.where(AuditLog.created_at >= start_at)
        if end_at is not None:
            stmt = stmt.where(AuditLog.created_at <= end_at)

        result = await self.session.scalars(
            stmt.order_by(AuditLog.created_at.desc(), AuditLog.id.asc())
            .limit(limit)
            .offset(offset)
        )
        return list(result.all())
