"""Audit-log API routes."""

from __future__ import annotations

from datetime import datetime
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Query

from app.api.v1.dependencies import AuditLogServiceDep, SuperAdminUserDep
from app.schemas.audit import AuditLogResponse

router = APIRouter(prefix="/admin/audit-logs", tags=["Audit Logs"])


@router.get("", response_model=list[AuditLogResponse])
async def list_audit_logs(
    actor: SuperAdminUserDep,
    service: AuditLogServiceDep,
    actor_user_id: UUID | None = None,
    action: str | None = None,
    target_type: str | None = None,
    target_id: UUID | None = None,
    start_at: datetime | None = None,
    end_at: datetime | None = None,
    limit: Annotated[int, Query(ge=1, le=500)] = 100,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> list[AuditLogResponse]:
    """List filtered organization audit logs."""
    return await service.list_for_super_admin(
        actor=actor,
        actor_user_id=actor_user_id,
        action=action,
        target_type=target_type,
        target_id=target_id,
        start_at=start_at,
        end_at=end_at,
        limit=limit,
        offset=offset,
    )
