"""Durable KB-service ingest outbox worker service."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any, Protocol
from uuid import UUID

import structlog
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.infrastructure.knowledgebase import BaseKnowledgebaseProvider
from app.infrastructure.storage.provider import StorageProvider
from app.models.uploads import KBIngestOutbox
from app.repositories.conversations import ConversationFileRepository
from app.repositories.knowledge_base import (
    KBDocumentEventRepository,
    KBDocumentRepository,
)
from app.repositories.uploads import KBIngestOutboxRepository
from app.schemas.knowledgebase import (
    KBDocumentIngestResponse,
    KBIngestRequest,
)
from app.services.kb_ingest_outbox.admin_upload_handler import AdminUploadHandler
from app.services.kb_ingest_outbox.conversation_file_handler import (
    ConversationFileHandler,
)
from app.services.kb_ingest_outbox.failure_policy import (
    SAFE_FAILURE_REASON,
    OutboxFailurePolicy,
    OutboxResourceMismatchError,
)

logger = structlog.get_logger(__name__)


class OutboxSourceHandler(Protocol):
    """Source-specific behavior needed by the outbox drain service."""

    source_type: str

    async def load_resource(self, row: KBIngestOutbox) -> object:
        """Return the trusted backend resource for this outbox row."""

    def linked_kb_service_document_id(
        self,
        row: KBIngestOutbox,
        resource: object,
    ) -> UUID | None:
        """Return an already-linked KB-service document ID if present."""

    async def build_ingest_request(
        self,
        row: KBIngestOutbox,
        resource: object,
    ) -> KBIngestRequest:
        """Build a trusted KB-service ingest request."""

    async def mark_dispatched(
        self,
        row: KBIngestOutbox,
        resource: object,
        response: KBDocumentIngestResponse | None,
    ) -> None:
        """Mirror dispatch state to the source resource."""

    async def load_resource_for_failure(self, row: KBIngestOutbox) -> object | None:
        """Load the source resource for best-effort failure mirroring."""

    async def mark_retry_scheduled(
        self,
        row: KBIngestOutbox,
        resource: object | None,
        *,
        next_attempt_at: datetime,
        attempt_count: int,
        exc: Exception,
    ) -> None:
        """Mirror retry state to the source resource."""

    async def mark_failed(
        self,
        row: KBIngestOutbox,
        resource: object | None,
        exc: Exception,
    ) -> None:
        """Mirror terminal failure state to the source resource."""


@dataclass(frozen=True)
class KbIngestOutboxDrainResult:
    """Summary of one drain pass."""

    processed: int = 0
    dispatched: int = 0
    retried: int = 0
    failed: int = 0
    next_attempt_at: datetime | None = None

    def to_task_payload(self) -> dict[str, Any]:
        """Return a JSON-safe Celery result payload."""
        return {
            "status": "complete",
            "processed": self.processed,
            "dispatched": self.dispatched,
            "retried": self.retried,
            "failed": self.failed,
            "next_attempt_at": (
                self.next_attempt_at.isoformat()
                if self.next_attempt_at is not None
                else None
            ),
            "next_countdown_seconds": self.next_countdown_seconds(),
        }

    def next_countdown_seconds(self) -> int | None:
        """Return seconds until the next attempt, clamped for Celery countdown."""
        if self.next_attempt_at is None:
            return None
        now = datetime.now(UTC)
        return max(0, int((self.next_attempt_at - now).total_seconds()))


@dataclass(frozen=True)
class _ProcessOutcome:
    """Internal single-row result flags."""

    dispatched: bool = False
    retried: bool = False
    failed: bool = False


class KbIngestOutboxService:
    """Drain durable backend-to-KB-service ingest handoff rows."""

    def __init__(
        self,
        session: AsyncSession,
        *,
        storage: StorageProvider,
        kb_provider: BaseKnowledgebaseProvider,
        settings: Settings,
        outbox_repo: KBIngestOutboxRepository | None = None,
        document_repo: KBDocumentRepository | None = None,
        document_event_repo: KBDocumentEventRepository | None = None,
        file_repo: ConversationFileRepository | None = None,
    ) -> None:
        self.session = session
        self.kb_provider = kb_provider
        self.settings = settings
        self.outbox_repo = outbox_repo or KBIngestOutboxRepository(session)
        self.document_repo = document_repo or KBDocumentRepository(session)
        self.document_event_repo = document_event_repo or KBDocumentEventRepository(
            session
        )
        self.file_repo = file_repo or ConversationFileRepository(session)
        self.failure_policy = OutboxFailurePolicy(settings)
        self.handlers: dict[str, OutboxSourceHandler] = {
            "admin_upload": AdminUploadHandler(
                storage=storage,
                document_repo=self.document_repo,
                document_event_repo=self.document_event_repo,
            ),
            "conversation_file": ConversationFileHandler(
                storage=storage,
                file_repo=self.file_repo,
            ),
        }

    async def drain_due(self, *, limit: int = 25) -> KbIngestOutboxDrainResult:
        """Drain due outbox rows one locked row at a time."""
        processed = 0
        dispatched = 0
        retried = 0
        failed = 0

        for _ in range(max(limit, 0)):
            outcome = await self._process_next_due_row()
            if outcome is None:
                break
            processed += 1
            if outcome.dispatched:
                dispatched += 1
            if outcome.retried:
                retried += 1
            if outcome.failed:
                failed += 1

        next_attempt_at = await self.outbox_repo.next_attempt_at()
        return KbIngestOutboxDrainResult(
            processed=processed,
            dispatched=dispatched,
            retried=retried,
            failed=failed,
            next_attempt_at=next_attempt_at,
        )

    async def _process_next_due_row(self) -> _ProcessOutcome | None:
        rows = await self.outbox_repo.list_due_for_update(
            now=datetime.now(UTC),
            limit=1,
        )
        if not rows:
            await self.session.rollback()
            return None

        row = rows[0]
        try:
            outcome = await self._process_locked_row(row)
        except Exception as exc:  # noqa: BLE001
            await self.session.rollback()
            logger.error(
                "kb_ingest_outbox_row_failed_unhandled",
                outbox_id=str(row.id),
                source_type=row.source_type,
                error_type=type(exc).__name__,
                exc_info=True,
            )
            raise
        else:
            await self.session.commit()
            return outcome

    async def _process_locked_row(
        self,
        row: KBIngestOutbox,
    ) -> _ProcessOutcome:
        handler = self._handler_for(row)
        try:
            resource = await handler.load_resource(row)
            linked_id = handler.linked_kb_service_document_id(row, resource)
            if linked_id is not None:
                await self.outbox_repo.mark_dispatched(
                    row,
                    kb_service_document_id=linked_id,
                    kb_task_id=row.kb_task_id,
                )
                await handler.mark_dispatched(row, resource, None)
                return _ProcessOutcome(dispatched=True)

            request = await handler.build_ingest_request(row, resource)
            response = await self.kb_provider.ingest_source(request)
            await self.outbox_repo.mark_dispatched(
                row,
                kb_service_document_id=response.kb_service_document_id,
                kb_task_id=response.task_id,
            )
            await handler.mark_dispatched(row, resource, response)
            logger.info(
                "kb_ingest_outbox_dispatched",
                outbox_id=str(row.id),
                source_type=row.source_type,
                kb_service_document_id=str(response.kb_service_document_id),
                kb_task_id=response.task_id,
            )
            return _ProcessOutcome(dispatched=True)
        except Exception as exc:  # noqa: BLE001
            return await self._record_failure(row, exc)

    async def _record_failure(
        self,
        row: KBIngestOutbox,
        exc: Exception,
    ) -> _ProcessOutcome:
        handler = self._handler_for(row)
        retryable = self.failure_policy.is_retryable(exc)
        counts_as_dispatch_attempt = self.failure_policy.counts_as_dispatch_attempt(
            exc
        )
        next_attempt_count = row.attempt_count + (
            1 if counts_as_dispatch_attempt else 0
        )
        failure_metadata = self.failure_policy.failure_metadata(
            exc,
            retryable=retryable,
            attempt_count=next_attempt_count,
        )
        resource = await handler.load_resource_for_failure(row)

        if retryable and next_attempt_count < self.settings.KB_RETRY_ATTEMPTS:
            next_attempt_at = datetime.now(UTC) + timedelta(
                seconds=self.failure_policy.retry_delay_seconds(next_attempt_count)
            )
            await self.outbox_repo.schedule_retry(
                row,
                next_attempt_at=next_attempt_at,
                failure_metadata=failure_metadata,
            )
            await handler.mark_retry_scheduled(
                row,
                resource,
                next_attempt_at=next_attempt_at,
                attempt_count=next_attempt_count,
                exc=exc,
            )
            logger.warning(
                "kb_ingest_outbox_retry_scheduled",
                outbox_id=str(row.id),
                source_type=row.source_type,
                error_type=type(exc).__name__,
                attempt_count=next_attempt_count,
                next_attempt_at=next_attempt_at.isoformat(),
            )
            return _ProcessOutcome(retried=True)

        await self.outbox_repo.mark_failed(
            row,
            failure_metadata=failure_metadata,
            error_message=SAFE_FAILURE_REASON,
            increment_attempt=counts_as_dispatch_attempt,
        )
        await handler.mark_failed(row, resource, exc)
        logger.warning(
            "kb_ingest_outbox_failed",
            outbox_id=str(row.id),
            source_type=row.source_type,
            error_type=type(exc).__name__,
            retryable=retryable,
        )
        return _ProcessOutcome(failed=True)

    def _handler_for(self, row: KBIngestOutbox) -> OutboxSourceHandler:
        handler = self.handlers.get(row.source_type)
        if handler is None:
            raise OutboxResourceMismatchError("Unsupported outbox source type")
        return handler
