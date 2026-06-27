"""Shared service-layer primitives for direct-to-storage uploads."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any, Literal
from uuid import UUID

import structlog

from app.core.exceptions import StorageError
from app.infrastructure.storage.provider import PresignedPostUpload, StorageProvider
from app.models.uploads import UploadRequest
from app.repositories.uploads import KBIngestOutboxRepository, UploadRequestRepository
from app.services.upload_validation import (
    raise_for_upload_verification_failure,
    validate_pending_upload_request,
)
from app.workers.dispatcher import (
    KbIngestOutboxTaskDispatcher,
    UploadRequestReconciliationTaskDispatcher,
)

logger = structlog.get_logger(__name__)

DirectUploadCompletionStatus = Literal["already_completed", "completed"]


@dataclass(frozen=True)
class DirectUploadSourceRef:
    """Trusted backend resource reference for one direct-upload request."""

    source_type: str
    kb_document_id: UUID | None = None
    conversation_file_id: UUID | None = None

    def __post_init__(self) -> None:
        has_document = self.kb_document_id is not None
        has_file = self.conversation_file_id is not None
        if self.source_type == "admin_upload":
            is_valid = has_document and not has_file
        elif self.source_type == "conversation_file":
            is_valid = has_file and not has_document
        else:
            is_valid = False
        if not is_valid:
            raise ValueError("Direct upload source must reference exactly one resource")

    @classmethod
    def admin_document(cls, document_id: UUID) -> DirectUploadSourceRef:
        """Return a trusted source reference for an admin KB document."""
        return cls(source_type="admin_upload", kb_document_id=document_id)

    @classmethod
    def conversation_file(cls, file_id: UUID) -> DirectUploadSourceRef:
        """Return a trusted source reference for a conversation file."""
        return cls(source_type="conversation_file", conversation_file_id=file_id)

    def to_repository_kwargs(self) -> dict[str, UUID | str | None]:
        """Return UploadRequest/KBIngestOutbox resource kwargs."""
        return {
            "source_type": self.source_type,
            "kb_document_id": self.kb_document_id,
            "conversation_file_id": self.conversation_file_id,
        }


@dataclass(frozen=True)
class DirectUploadCompletionResult:
    """Result of completing a direct-upload request."""

    status: DirectUploadCompletionStatus
    upload_request: UploadRequest


class DirectUploadWorkflow:
    """Shared orchestration for backend-owned direct-upload lifecycle steps."""

    def __init__(
        self,
        *,
        storage: StorageProvider,
        upload_request_repo: UploadRequestRepository,
        outbox_repo: KBIngestOutboxRepository,
        outbox_dispatcher: KbIngestOutboxTaskDispatcher,
        upload_reconciliation_dispatcher: UploadRequestReconciliationTaskDispatcher,
    ) -> None:
        self.storage = storage
        self.upload_request_repo = upload_request_repo
        self.outbox_repo = outbox_repo
        self.outbox_dispatcher = outbox_dispatcher
        self.upload_reconciliation_dispatcher = upload_reconciliation_dispatcher

    async def create_presigned_post(
        self,
        *,
        storage_key: str,
        content_type: str,
        size_bytes: int,
        error_message: str,
        log_event: str,
        log_context: dict[str, Any],
    ) -> PresignedPostUpload:
        """Create a browser upload contract and sanitize storage failures."""
        try:
            return await self.storage.create_presigned_post(
                key=storage_key,
                content_type=content_type,
                max_size_bytes=size_bytes,
            )
        except Exception as exc:
            logger.warning(
                log_event,
                **log_context,
                error_type=type(exc).__name__,
            )
            raise StorageError(error_message) from exc

    async def record_upload_request(
        self,
        *,
        organization_id: UUID,
        requested_by: UUID | None,
        source: DirectUploadSourceRef,
        filename: str,
        content_type: str,
        size_bytes: int,
        storage_key: str,
        expires_at: datetime,
        request_metadata: dict[str, Any] | None = None,
    ) -> UploadRequest:
        """Persist a direct-upload request without committing."""
        return await self.upload_request_repo.create(
            organization_id=organization_id,
            requested_by=requested_by,
            filename=filename,
            content_type=content_type,
            size_bytes=size_bytes,
            storage_key=storage_key,
            expires_at=expires_at,
            request_metadata=request_metadata,
            **source.to_repository_kwargs(),
        )

    async def complete_upload_request(
        self,
        upload_request: UploadRequest,
    ) -> DirectUploadCompletionResult:
        """Verify storage and mark a pending direct-upload request completed."""
        if upload_request.status == "completed":
            return DirectUploadCompletionResult(
                status="already_completed",
                upload_request=upload_request,
            )

        validate_pending_upload_request(upload_request.expires_at)
        verification = await self.storage.verify_object(
            key=upload_request.storage_key,
            expected_size_bytes=upload_request.size_bytes,
            expected_content_type=upload_request.content_type,
        )
        raise_for_upload_verification_failure(verification.status)

        completed = await self.upload_request_repo.mark_completed(upload_request)
        return DirectUploadCompletionResult(
            status="completed",
            upload_request=completed,
        )

    async def enqueue_ingest(
        self,
        *,
        organization_id: UUID,
        source: DirectUploadSourceRef,
    ) -> None:
        """Create or reuse a durable KB ingest outbox row without committing."""
        await self.outbox_repo.enqueue(
            organization_id=organization_id,
            **source.to_repository_kwargs(),
        )

    def dispatch_kb_ingest_outbox(self, *, log_context: dict[str, Any]) -> None:
        """Dispatch the KB ingest outbox worker after the DB transaction commits."""
        try:
            self.outbox_dispatcher.dispatch()
        except Exception as exc:  # noqa: BLE001
            logger.warning(
                "kb_ingest_outbox_dispatch_failed",
                **log_context,
                error_type=type(exc).__name__,
            )

    def dispatch_upload_reconciliation(
        self,
        *,
        expires_at: datetime,
        log_context: dict[str, Any],
    ) -> None:
        """Schedule reconciliation for a pending direct-upload request expiration."""
        try:
            self.upload_reconciliation_dispatcher.dispatch(
                countdown=self._countdown_until(expires_at)
            )
        except Exception as exc:  # noqa: BLE001
            logger.warning(
                "upload_reconciliation_dispatch_failed",
                **log_context,
                error_type=type(exc).__name__,
            )

    @staticmethod
    def _countdown_until(target: datetime) -> int:
        return max(0, int((target - datetime.now(UTC)).total_seconds()))
