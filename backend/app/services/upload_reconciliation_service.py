"""Maintenance service for expired direct-upload requests."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any, Literal

import structlog
from sqlalchemy.ext.asyncio import AsyncSession

from app.infrastructure.storage.provider import StorageProvider
from app.models.conversations import Conversation, ConversationFile
from app.models.knowledge_base import KBDocument
from app.models.uploads import UploadRequest
from app.repositories.conversations import ConversationFileRepository
from app.repositories.knowledge_base import (
    KBDocumentEventRepository,
    KBDocumentRepository,
)
from app.repositories.uploads import KBIngestOutboxRepository, UploadRequestRepository

logger = structlog.get_logger(__name__)

SAFE_UPLOAD_EXPIRED_REASON = "Upload request expired before the file was received."

_CleanupStatus = Literal["deleted", "missing", "failed", "skipped"]


@dataclass(frozen=True)
class UploadRequestReconciliationResult:
    """Summary of one expired-upload reconciliation pass."""

    processed: int = 0
    expired: int = 0
    resources_failed: int = 0
    objects_deleted: int = 0
    objects_missing: int = 0
    cleanup_failed: int = 0
    skipped: int = 0
    admin_upload_pending_count: int = 0
    conversation_upload_pending_count: int = 0
    outbox_due_backlog: int = 0
    next_expiration_at: datetime | None = None

    def to_task_payload(self) -> dict[str, Any]:
        """Return a JSON-safe Celery result payload."""
        return {
            "status": "complete",
            "processed": self.processed,
            "expired": self.expired,
            "resources_failed": self.resources_failed,
            "objects_deleted": self.objects_deleted,
            "objects_missing": self.objects_missing,
            "cleanup_failed": self.cleanup_failed,
            "skipped": self.skipped,
            "admin_upload_pending_count": self.admin_upload_pending_count,
            "conversation_upload_pending_count": (
                self.conversation_upload_pending_count
            ),
            "outbox_due_backlog": self.outbox_due_backlog,
            "next_expiration_at": (
                self.next_expiration_at.isoformat()
                if self.next_expiration_at is not None
                else None
            ),
            "next_countdown_seconds": self.next_countdown_seconds(),
        }

    def next_countdown_seconds(self) -> int | None:
        """Return seconds until the next pending expiration."""
        if self.next_expiration_at is None:
            return None
        now = datetime.now(UTC)
        return max(0, int((self.next_expiration_at - now).total_seconds()))


@dataclass(frozen=True)
class _CleanupOutcome:
    """Result of storage cleanup for one known upload intent key."""

    status: _CleanupStatus


@dataclass(frozen=True)
class _ProcessOutcome:
    """Internal single-row result flags."""

    expired: bool = False
    resource_failed: bool = False
    cleanup_status: _CleanupStatus = "skipped"
    skipped: bool = False


class UploadRequestReconciliationService:
    """Expire stale direct-upload intents and clean known orphan objects."""

    def __init__(
        self,
        session: AsyncSession,
        *,
        storage: StorageProvider,
        upload_request_repo: UploadRequestRepository | None = None,
        document_repo: KBDocumentRepository | None = None,
        document_event_repo: KBDocumentEventRepository | None = None,
        file_repo: ConversationFileRepository | None = None,
        outbox_repo: KBIngestOutboxRepository | None = None,
    ) -> None:
        self.session = session
        self.storage = storage
        self.upload_request_repo = upload_request_repo or UploadRequestRepository(
            session
        )
        self.document_repo = document_repo or KBDocumentRepository(session)
        self.document_event_repo = document_event_repo or KBDocumentEventRepository(
            session
        )
        self.file_repo = file_repo or ConversationFileRepository(session)
        self.outbox_repo = outbox_repo or KBIngestOutboxRepository(session)

    async def reconcile_expired(
        self,
        *,
        limit: int = 100,
    ) -> UploadRequestReconciliationResult:
        """Reconcile expired pending upload requests one locked row at a time."""
        processed = 0
        expired = 0
        resources_failed = 0
        objects_deleted = 0
        objects_missing = 0
        cleanup_failed = 0
        skipped = 0

        for _ in range(max(limit, 0)):
            outcome = await self._process_next_expired_request()
            if outcome is None:
                break

            processed += 1
            if outcome.expired:
                expired += 1
            if outcome.resource_failed:
                resources_failed += 1
            if outcome.cleanup_status == "deleted":
                objects_deleted += 1
            elif outcome.cleanup_status == "missing":
                objects_missing += 1
            elif outcome.cleanup_status == "failed":
                cleanup_failed += 1
            if outcome.skipped:
                skipped += 1

        now = datetime.now(UTC)
        next_expiration_at = await self.upload_request_repo.next_pending_expiration_at()
        result = UploadRequestReconciliationResult(
            processed=processed,
            expired=expired,
            resources_failed=resources_failed,
            objects_deleted=objects_deleted,
            objects_missing=objects_missing,
            cleanup_failed=cleanup_failed,
            skipped=skipped,
            admin_upload_pending_count=await self.document_repo.count_by_status(
                processing_status="upload_pending",
            ),
            conversation_upload_pending_count=await self.file_repo.count_by_status(
                extraction_status="upload_pending",
            ),
            outbox_due_backlog=await self.outbox_repo.count_due(now=now),
            next_expiration_at=next_expiration_at,
        )
        logger.info(
            "upload_request_reconciliation_completed",
            **result.to_task_payload(),
        )
        return result

    async def _process_next_expired_request(self) -> _ProcessOutcome | None:
        rows = await self.upload_request_repo.list_expired_pending_requests(
            now=datetime.now(UTC),
            limit=1,
            for_update=True,
        )
        if not rows:
            return None

        request = rows[0]
        try:
            outcome = await self._process_locked_request(request)
        except Exception:  # noqa: BLE001
            await self.session.rollback()
            logger.error(
                "upload_request_reconciliation_unhandled_error",
                upload_request_id=str(request.id),
                source_type=request.source_type,
                exc_info=True,
            )
            raise

        await self.session.commit()
        return outcome

    async def _process_locked_request(
        self,
        request: UploadRequest,
    ) -> _ProcessOutcome:
        if request.source_type == "admin_upload":
            return await self._process_admin_upload(request)
        if request.source_type == "conversation_file":
            return await self._process_conversation_file(request)

        await self.upload_request_repo.mark_expired(
            request,
            metadata=self._request_metadata(
                request,
                failure_code="unsupported_source_type",
                cleanup_status="skipped",
            ),
        )
        logger.warning(
            "upload_request_reconciliation_unsupported_source_type",
            upload_request_id=str(request.id),
            source_type=request.source_type,
        )
        return _ProcessOutcome(expired=True, skipped=True)

    async def _process_admin_upload(
        self,
        request: UploadRequest,
    ) -> _ProcessOutcome:
        if request.kb_document_id is None:
            return await self._expire_missing_resource(request)

        document = await self.document_repo.get(request.kb_document_id)
        if document is None:
            return await self._expire_missing_resource(request)
        if document.processing_status != "upload_pending":
            return await self._expire_already_transitioned_request(
                request,
                resource_status=document.processing_status,
            )

        cleanup = await self._cleanup_known_intent_object(request)
        await self.upload_request_repo.mark_expired(
            request,
            metadata=self._request_metadata(
                request,
                failure_code="upload_request_expired",
                cleanup_status=cleanup.status,
            ),
        )
        await self.document_repo.update_status(
            document,
            processing_status="failed",
            failure_reason=SAFE_UPLOAD_EXPIRED_REASON,
        )
        await self.document_event_repo.create(
            document_id=document.id,
            event_type="document.upload_expired",
            status="failed",
            message=SAFE_UPLOAD_EXPIRED_REASON,
            metadata={
                "upload_request_id": str(request.id),
                "failure_code": "upload_request_expired",
                "cleanup_status": cleanup.status,
                "expired_at": datetime.now(UTC).isoformat(),
            },
        )
        self._log_resource_expired(
            request,
            document=document,
            cleanup_status=cleanup.status,
        )
        return _ProcessOutcome(
            expired=True,
            resource_failed=True,
            cleanup_status=cleanup.status,
        )

    async def _process_conversation_file(
        self,
        request: UploadRequest,
    ) -> _ProcessOutcome:
        if request.conversation_file_id is None:
            return await self._expire_missing_resource(request)

        file_with_conversation = await self.file_repo.get_with_conversation(
            request.conversation_file_id
        )
        if file_with_conversation is None:
            return await self._expire_missing_resource(request)

        file, conversation = file_with_conversation
        if conversation.organization_id != request.organization_id:
            return await self._expire_already_transitioned_request(
                request,
                resource_status="organization_mismatch",
            )
        if file.extraction_status != "upload_pending":
            return await self._expire_already_transitioned_request(
                request,
                resource_status=file.extraction_status,
            )

        cleanup = await self._cleanup_known_intent_object(request)
        await self.upload_request_repo.mark_expired(
            request,
            metadata=self._request_metadata(
                request,
                failure_code="upload_request_expired",
                cleanup_status=cleanup.status,
            ),
        )
        await self.file_repo.update_extraction_status(
            file,
            extraction_status="failed",
            extraction_metadata=self._file_failure_metadata(file, request, cleanup),
            error_message=SAFE_UPLOAD_EXPIRED_REASON,
        )
        self._log_resource_expired(
            request,
            file=file,
            conversation=conversation,
            cleanup_status=cleanup.status,
        )
        return _ProcessOutcome(
            expired=True,
            resource_failed=True,
            cleanup_status=cleanup.status,
        )

    async def _expire_missing_resource(
        self,
        request: UploadRequest,
    ) -> _ProcessOutcome:
        await self.upload_request_repo.mark_expired(
            request,
            metadata=self._request_metadata(
                request,
                failure_code="resource_missing",
                cleanup_status="skipped",
            ),
        )
        logger.warning(
            "upload_request_reconciliation_resource_missing",
            upload_request_id=str(request.id),
            source_type=request.source_type,
        )
        return _ProcessOutcome(expired=True, skipped=True)

    async def _expire_already_transitioned_request(
        self,
        request: UploadRequest,
        *,
        resource_status: str,
    ) -> _ProcessOutcome:
        await self.upload_request_repo.mark_expired(
            request,
            metadata=self._request_metadata(
                request,
                failure_code="resource_already_transitioned",
                cleanup_status="skipped",
                extra={"resource_status": resource_status},
            ),
        )
        logger.info(
            "upload_request_reconciliation_skipped_resource_state",
            upload_request_id=str(request.id),
            source_type=request.source_type,
            resource_status=resource_status,
        )
        return _ProcessOutcome(expired=True, skipped=True)

    async def _cleanup_known_intent_object(
        self,
        request: UploadRequest,
    ) -> _CleanupOutcome:
        try:
            metadata = await self.storage.get_object_metadata(request.storage_key)
        except Exception as exc:  # noqa: BLE001
            logger.warning(
                "upload_request_cleanup_head_failed",
                upload_request_id=str(request.id),
                source_type=request.source_type,
                error_type=type(exc).__name__,
            )
            return _CleanupOutcome(status="failed")

        if metadata is None:
            return _CleanupOutcome(status="missing")

        try:
            await self.storage.delete_file(request.storage_key)
        except Exception as exc:  # noqa: BLE001
            logger.warning(
                "upload_request_cleanup_delete_failed",
                upload_request_id=str(request.id),
                source_type=request.source_type,
                error_type=type(exc).__name__,
            )
            return _CleanupOutcome(status="failed")

        return _CleanupOutcome(status="deleted")

    @staticmethod
    def _request_metadata(
        request: UploadRequest,
        *,
        failure_code: str,
        cleanup_status: _CleanupStatus,
        extra: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        metadata = {
            **request.request_metadata,
            "failure_code": failure_code,
            "cleanup_status": cleanup_status,
            "expired_at": datetime.now(UTC).isoformat(),
        }
        if extra is not None:
            metadata.update(extra)
        return metadata

    @staticmethod
    def _file_failure_metadata(
        file: ConversationFile,
        request: UploadRequest,
        cleanup: _CleanupOutcome,
    ) -> dict[str, Any]:
        return {
            **file.extraction_metadata,
            "failure_code": "upload_request_expired",
            "upload_request_id": str(request.id),
            "cleanup_status": cleanup.status,
            "expired_at": datetime.now(UTC).isoformat(),
        }

    @staticmethod
    def _log_resource_expired(
        request: UploadRequest,
        *,
        cleanup_status: _CleanupStatus,
        document: KBDocument | None = None,
        file: ConversationFile | None = None,
        conversation: Conversation | None = None,
    ) -> None:
        logger.info(
            "upload_request_resource_expired",
            upload_request_id=str(request.id),
            source_type=request.source_type,
            kb_document_id=str(document.id) if document is not None else None,
            conversation_file_id=str(file.id) if file is not None else None,
            conversation_id=(
                str(conversation.id) if conversation is not None else None
            ),
            cleanup_status=cleanup_status,
        )
