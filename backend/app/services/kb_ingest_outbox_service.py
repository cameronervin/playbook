"""Durable KB-service ingest outbox worker service."""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import UUID

import structlog
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.core.exceptions import (
    AppError,
    KBAuthError,
    KBConfigError,
    KBConnectionError,
    KBTimeoutError,
    KBValidationError,
    StorageError,
)
from app.core.log_redaction import redact_string
from app.infrastructure.knowledgebase import BaseKnowledgebaseProvider
from app.infrastructure.storage.provider import StorageProvider
from app.models.conversations import Conversation, ConversationFile
from app.models.knowledge_base import KBDocument
from app.models.uploads import KBIngestOutbox
from app.repositories.conversations import ConversationFileRepository
from app.repositories.knowledge_base import (
    KBDocumentEventRepository,
    KBDocumentRepository,
)
from app.repositories.uploads import KBIngestOutboxRepository
from app.schemas.knowledgebase import (
    KBConversationFileIngestRequest,
    KBDocumentIngestRequest,
    KBDocumentIngestResponse,
    KBIngestRequest,
)

logger = structlog.get_logger(__name__)

_URL_RE = re.compile(r"https?://[^\s,)]+")
_SAFE_FAILURE_REASON = "KB ingestion dispatch failed"
_RETRYABLE_KB_ERRORS = (KBConnectionError, KBTimeoutError)
_TERMINAL_KB_ERRORS = (KBAuthError, KBValidationError, KBConfigError)


class OutboxResourceMissingError(RuntimeError):
    """Raised when an outbox row no longer has its backend resource."""


class OutboxResourceMismatchError(RuntimeError):
    """Raised when an outbox row disagrees with trusted backend metadata."""


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
        self.storage = storage
        self.kb_provider = kb_provider
        self.settings = settings
        self.outbox_repo = outbox_repo or KBIngestOutboxRepository(session)
        self.document_repo = document_repo or KBDocumentRepository(session)
        self.document_event_repo = document_event_repo or KBDocumentEventRepository(
            session
        )
        self.file_repo = file_repo or ConversationFileRepository(session)

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
        try:
            resource = await self._load_resource(row)
            linked_id = self._linked_kb_service_document_id(row, resource)
            if linked_id is not None:
                await self.outbox_repo.mark_dispatched(
                    row,
                    kb_service_document_id=linked_id,
                    kb_task_id=row.kb_task_id,
                )
                await self._mark_resource_dispatched(resource, None, row)
                return _ProcessOutcome(dispatched=True)

            request = await self._build_ingest_request(row, resource)
            response = await self.kb_provider.ingest_source(request)
            await self.outbox_repo.mark_dispatched(
                row,
                kb_service_document_id=response.kb_service_document_id,
                kb_task_id=response.task_id,
            )
            await self._mark_resource_dispatched(resource, response, row)
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

    async def _load_resource(
        self,
        row: KBIngestOutbox,
    ) -> KBDocument | tuple[ConversationFile, Conversation]:
        if row.source_type == "admin_upload":
            if row.kb_document_id is None:
                raise OutboxResourceMissingError("Outbox row has no KB document")
            document = await self.document_repo.get(row.kb_document_id)
            if document is None:
                raise OutboxResourceMissingError("KB document is missing")
            if document.organization_id != row.organization_id:
                raise OutboxResourceMismatchError(
                    "Outbox organization does not match KB document"
                )
            return document

        if row.source_type == "conversation_file":
            if row.conversation_file_id is None:
                raise OutboxResourceMissingError(
                    "Outbox row has no conversation file"
                )
            file_with_conversation = await self.file_repo.get_with_conversation(
                row.conversation_file_id
            )
            if file_with_conversation is None:
                raise OutboxResourceMissingError("Conversation file is missing")
            _file, conversation = file_with_conversation
            if conversation.organization_id != row.organization_id:
                raise OutboxResourceMismatchError(
                    "Outbox organization does not match conversation"
                )
            return file_with_conversation

        raise OutboxResourceMismatchError("Unsupported outbox source type")

    async def _build_ingest_request(
        self,
        row: KBIngestOutbox,
        resource: KBDocument | tuple[ConversationFile, Conversation],
    ) -> KBIngestRequest:
        if row.source_type == "admin_upload":
            if not isinstance(resource, KBDocument):
                raise OutboxResourceMismatchError("Admin row resolved non-document")
            source_uri = await self.storage.get_presigned_url(
                resource.storage_key,
                download_filename=resource.filename,
            )
            return KBDocumentIngestRequest(
                organization_id=resource.organization_id,
                playbook_document_id=resource.id,
                source_uri=source_uri,
                filename=resource.filename,
                content_type=resource.content_type,
                size_bytes=resource.size_bytes,
                source_title=resource.title,
                source_date=resource.source_date,
                is_official=resource.is_official,
                priority=resource.priority,
                visibility_policy=resource.visibility_policy,
                metadata_tags=resource.metadata_tags,
            )

        if not isinstance(resource, tuple):
            raise OutboxResourceMismatchError("Conversation row resolved non-file")
        file, conversation = resource
        source_uri = await self.storage.get_presigned_url(
            file.storage_key,
            download_filename=file.filename,
        )
        return KBConversationFileIngestRequest(
            organization_id=conversation.organization_id,
            conversation_id=conversation.id,
            conversation_file_id=file.id,
            source_uri=source_uri,
            filename=file.filename,
            content_type=file.content_type,
            size_bytes=file.size_bytes,
            source_title=file.filename,
        )

    async def _mark_resource_dispatched(
        self,
        resource: KBDocument | tuple[ConversationFile, Conversation],
        response: KBDocumentIngestResponse | None,
        row: KBIngestOutbox,
    ) -> None:
        if isinstance(resource, KBDocument):
            if response is not None:
                await self.document_repo.link_kb_service_document(
                    resource,
                    kb_service_document_id=response.kb_service_document_id,
                )
            if resource.processing_status == "uploaded":
                await self.document_repo.update_status(
                    resource,
                    processing_status="processing",
                    failure_reason=None,
                )
            await self.document_event_repo.create(
                document_id=resource.id,
                event_type="ingestion.dispatched",
                status=resource.processing_status,
                message=None,
                metadata={
                    "outbox_id": str(row.id),
                    "kb_service_document_id": str(
                        response.kb_service_document_id
                        if response is not None
                        else row.kb_service_document_id
                    ),
                    "task_id": response.task_id if response is not None else row.kb_task_id,
                },
            )
            return

        file, conversation = resource
        extraction_metadata = {
            "source_type": "conversation_file",
            "conversation_id": str(conversation.id),
            "conversation_file_id": str(file.id),
            "kb_service_document_id": str(
                response.kb_service_document_id
                if response is not None
                else row.kb_service_document_id
            ),
            "task_id": response.task_id if response is not None else row.kb_task_id,
            "kb_status": response.status if response is not None else "pending",
        }
        if response is not None:
            await self.file_repo.update_ingestion_mirror(
                file,
                kb_service_document_id=response.kb_service_document_id,
            )
        await self.file_repo.update_extraction_status(
            file,
            extraction_status=(
                "extracting" if file.extraction_status == "uploaded" else file.extraction_status
            ),
            extraction_metadata=extraction_metadata,
            error_message=None,
        )

    async def _record_failure(
        self,
        row: KBIngestOutbox,
        exc: Exception,
    ) -> _ProcessOutcome:
        retryable = self._is_retryable(exc)
        counts_as_dispatch_attempt = not isinstance(
            exc,
            (OutboxResourceMissingError, OutboxResourceMismatchError),
        )
        next_attempt_count = row.attempt_count + (
            1 if counts_as_dispatch_attempt else 0
        )
        failure_metadata = self._failure_metadata(
            exc,
            retryable=retryable,
            attempt_count=next_attempt_count,
        )
        resource = await self._load_resource_for_failure(row)

        if retryable and next_attempt_count < self.settings.KB_RETRY_ATTEMPTS:
            next_attempt_at = datetime.now(UTC) + timedelta(
                seconds=self._retry_delay_seconds(next_attempt_count)
            )
            await self.outbox_repo.schedule_retry(
                row,
                next_attempt_at=next_attempt_at,
                failure_metadata=failure_metadata,
            )
            if isinstance(resource, KBDocument):
                await self.document_event_repo.create(
                    document_id=resource.id,
                    event_type="ingestion.retry_scheduled",
                    status=resource.processing_status,
                    message=None,
                    metadata={
                        "outbox_id": str(row.id),
                        "attempt_count": next_attempt_count,
                        "next_attempt_at": next_attempt_at.isoformat(),
                        "error_type": type(exc).__name__,
                    },
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
            error_message=_SAFE_FAILURE_REASON,
            increment_attempt=counts_as_dispatch_attempt,
        )
        await self._mark_resource_failed(resource, row, exc)
        logger.warning(
            "kb_ingest_outbox_failed",
            outbox_id=str(row.id),
            source_type=row.source_type,
            error_type=type(exc).__name__,
            retryable=retryable,
        )
        return _ProcessOutcome(failed=True)

    async def _load_resource_for_failure(
        self,
        row: KBIngestOutbox,
    ) -> KBDocument | tuple[ConversationFile, Conversation] | None:
        if row.source_type == "admin_upload" and row.kb_document_id is not None:
            return await self.document_repo.get(row.kb_document_id)
        if (
            row.source_type == "conversation_file"
            and row.conversation_file_id is not None
        ):
            return await self.file_repo.get_with_conversation(row.conversation_file_id)
        return None

    async def _mark_resource_failed(
        self,
        resource: KBDocument | tuple[ConversationFile, Conversation] | None,
        row: KBIngestOutbox,
        exc: Exception,
    ) -> None:
        if isinstance(resource, KBDocument):
            await self.document_repo.update_status(
                resource,
                processing_status="failed",
                failure_reason=_SAFE_FAILURE_REASON,
            )
            await self.document_event_repo.create(
                document_id=resource.id,
                event_type="ingestion.failed",
                status="failed",
                message=_SAFE_FAILURE_REASON,
                metadata={
                    "outbox_id": str(row.id),
                    "error_type": type(exc).__name__,
                    "attempt_count": row.attempt_count,
                },
            )
            return

        if isinstance(resource, tuple):
            file, _conversation = resource
            await self.file_repo.update_extraction_status(
                file,
                extraction_status="failed",
                extraction_metadata={
                    "source_type": "conversation_file",
                    "conversation_file_id": str(file.id),
                    "dispatch_error_type": type(exc).__name__,
                },
                error_message=_SAFE_FAILURE_REASON,
            )

    def _failure_metadata(
        self,
        exc: Exception,
        *,
        retryable: bool,
        attempt_count: int,
    ) -> dict[str, Any]:
        return {
            "error_type": type(exc).__name__,
            "retryable": retryable,
            "attempt_count": attempt_count,
            "max_attempts": self.settings.KB_RETRY_ATTEMPTS,
            "message": self._safe_message(exc),
        }

    @staticmethod
    def _safe_message(exc: Exception) -> str:
        message = redact_string(str(exc))
        if _URL_RE.search(message):
            return _SAFE_FAILURE_REASON
        return message[:500] or _SAFE_FAILURE_REASON

    @staticmethod
    def _is_retryable(exc: Exception) -> bool:
        if isinstance(exc, _TERMINAL_KB_ERRORS):
            return False
        if isinstance(exc, _RETRYABLE_KB_ERRORS):
            return True
        if isinstance(exc, StorageError):
            return exc.retryable
        if isinstance(exc, AppError):
            return exc.retryable
        return False

    def _retry_delay_seconds(self, attempt_count: int) -> int:
        delay = self.settings.KB_RETRY_BACKOFF_BASE * attempt_count
        return min(delay, self.settings.KB_RETRY_BACKOFF_CAP)

    @staticmethod
    def _linked_kb_service_document_id(
        row: KBIngestOutbox,
        resource: KBDocument | tuple[ConversationFile, Conversation],
    ) -> UUID | None:
        if row.kb_service_document_id is not None:
            return row.kb_service_document_id
        if isinstance(resource, KBDocument):
            return resource.kb_service_document_id
        file, _conversation = resource
        return file.kb_service_document_id
