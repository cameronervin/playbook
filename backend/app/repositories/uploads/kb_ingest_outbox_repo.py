"""Repository for durable KB-service ingest outbox rows."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any
from uuid import UUID

from fastapi import Depends
from sqlalchemy import Select, func, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.infrastructure.db.session import get_db
from app.models.uploads import KBIngestOutbox


class KBIngestOutboxRepository:
    """Data access for durable KB-service ingest outbox rows."""

    DUE_STATUSES = ("pending", "retrying")

    def __init__(self, session: AsyncSession = Depends(get_db)) -> None:
        self.session = session

    async def enqueue(
        self,
        *,
        organization_id: UUID,
        source_type: str,
        kb_document_id: UUID | None = None,
        conversation_file_id: UUID | None = None,
        next_attempt_at: datetime | None = None,
        failure_metadata: dict[str, Any] | None = None,
    ) -> KBIngestOutbox:
        """Create one outbox row per backend resource, returning existing rows."""
        values: dict[str, Any] = {
            "organization_id": organization_id,
            "source_type": source_type,
            "kb_document_id": kb_document_id,
            "conversation_file_id": conversation_file_id,
        }
        if next_attempt_at is not None:
            values["next_attempt_at"] = next_attempt_at
        if failure_metadata is not None:
            values["failure_metadata"] = failure_metadata

        stmt = insert(KBIngestOutbox).values(**values)
        if source_type == "admin_upload":
            stmt = stmt.on_conflict_do_nothing(
                index_elements=["source_type", "kb_document_id"]
            )
        else:
            stmt = stmt.on_conflict_do_nothing(
                index_elements=["source_type", "conversation_file_id"]
            )
        await self.session.execute(stmt)
        await self.session.flush()

        row = await self.get_for_resource(
            source_type=source_type,
            kb_document_id=kb_document_id,
            conversation_file_id=conversation_file_id,
        )
        if row is None:
            raise RuntimeError("Failed to enqueue KB ingest outbox row")
        return row

    async def get_for_resource(
        self,
        *,
        source_type: str,
        kb_document_id: UUID | None = None,
        conversation_file_id: UUID | None = None,
    ) -> KBIngestOutbox | None:
        """Return an outbox row for the exact backend source resource."""
        stmt = select(KBIngestOutbox).where(KBIngestOutbox.source_type == source_type)
        if source_type == "admin_upload":
            stmt = stmt.where(KBIngestOutbox.kb_document_id == kb_document_id)
        else:
            stmt = stmt.where(
                KBIngestOutbox.conversation_file_id == conversation_file_id
            )

        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    @classmethod
    def due_rows_statement(
        cls,
        *,
        now: datetime,
        limit: int,
    ) -> Select[tuple[KBIngestOutbox]]:
        """Build the row-locking due outbox query."""
        return (
            select(KBIngestOutbox)
            .where(
                KBIngestOutbox.status.in_(cls.DUE_STATUSES),
                KBIngestOutbox.next_attempt_at <= now,
            )
            .order_by(KBIngestOutbox.next_attempt_at.asc(), KBIngestOutbox.id.asc())
            .limit(limit)
            .with_for_update(skip_locked=True)
        )

    async def list_due_for_update(
        self,
        *,
        now: datetime,
        limit: int = 100,
    ) -> list[KBIngestOutbox]:
        """Return due outbox rows locked for this worker transaction."""
        result = await self.session.scalars(
            self.due_rows_statement(now=now, limit=limit)
        )
        return list(result.all())

    async def mark_dispatched(
        self,
        row: KBIngestOutbox,
        *,
        kb_service_document_id: UUID,
        kb_task_id: str | None,
        dispatched_at: datetime | None = None,
    ) -> KBIngestOutbox:
        """Mark an outbox row dispatched to KB-service without committing."""
        now = dispatched_at or datetime.now(UTC)
        row.status = "dispatched"
        row.attempt_count += 1
        row.last_attempt_at = now
        row.dispatched_at = now
        row.kb_service_document_id = kb_service_document_id
        row.kb_task_id = kb_task_id
        await self.session.flush()
        await self.session.refresh(row)
        return row

    async def schedule_retry(
        self,
        row: KBIngestOutbox,
        *,
        next_attempt_at: datetime,
        failure_metadata: dict[str, Any] | None = None,
        attempted_at: datetime | None = None,
    ) -> KBIngestOutbox:
        """Record a retryable dispatch failure without committing."""
        row.status = "retrying"
        row.attempt_count += 1
        row.last_attempt_at = attempted_at or datetime.now(UTC)
        row.next_attempt_at = next_attempt_at
        if failure_metadata is not None:
            row.failure_metadata = failure_metadata
        await self.session.flush()
        await self.session.refresh(row)
        return row

    async def mark_failed(
        self,
        row: KBIngestOutbox,
        *,
        failure_metadata: dict[str, Any] | None = None,
        error_message: str | None = None,
        increment_attempt: bool = False,
        attempted_at: datetime | None = None,
    ) -> KBIngestOutbox:
        """Mark an outbox row terminally failed without committing."""
        row.status = "failed"
        if increment_attempt:
            row.attempt_count += 1
        row.last_attempt_at = attempted_at or datetime.now(UTC)
        if failure_metadata is not None:
            row.failure_metadata = failure_metadata
        if error_message is not None:
            row.error_message = error_message
        await self.session.flush()
        await self.session.refresh(row)
        return row

    async def next_attempt_at(self) -> datetime | None:
        """Return the next pending/retrying outbox attempt timestamp."""
        result = await self.session.scalar(
            select(func.min(KBIngestOutbox.next_attempt_at)).where(
                KBIngestOutbox.status.in_(self.DUE_STATUSES)
            )
        )
        return result

    async def count_due(self, *, now: datetime) -> int:
        """Return the due pending/retrying outbox row count."""
        result = await self.session.scalar(
            select(func.count())
            .select_from(KBIngestOutbox)
            .where(
                KBIngestOutbox.status.in_(self.DUE_STATUSES),
                KBIngestOutbox.next_attempt_at <= now,
            )
        )
        return int(result or 0)
