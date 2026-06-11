"""Knowledge-base document control-plane services."""

from __future__ import annotations

import hashlib
import hmac
import time
from dataclasses import dataclass
from datetime import UTC, date, datetime
from typing import Any, BinaryIO
from uuid import UUID

import structlog
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.core.exceptions import (
    ForbiddenError,
    NotFoundError,
    UnsupportedFileTypeError,
)
from app.infrastructure.knowledgebase import BaseKnowledgebaseProvider
from app.infrastructure.storage.paths import kb_original_file_key
from app.infrastructure.storage.provider import StorageProvider
from app.models.identity import User
from app.models.knowledge_base import KBDocument, KBDocumentEvent
from app.repositories.knowledge_base import (
    KBDocumentEventRepository,
    KBDocumentRepository,
)
from app.schemas.kb_documents import (
    KBDocumentEventResponse,
    KBDocumentMetadataUpdateRequest,
    KBDocumentResponse,
    KBWebhookPayload,
    KBWebhookResponse,
)
from app.schemas.knowledgebase import KBDocumentIngestRequest
from app.services.audit_service import AuditLogService

logger = structlog.get_logger(__name__)

SUPPORTED_KB_CONTENT_TYPES = {
    "application/pdf",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "application/vnd.openxmlformats-officedocument.presentationml.presentation",
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
}

_TERMINAL_READY = {"success", "succeeded", "complete", "completed", "ready"}
_TERMINAL_FAILED = {"failure", "failed", "error", "revoked"}
_PROCESSING = {"started", "processing", "parsing", "chunking", "embedding", "loading"}


@dataclass(frozen=True)
class KBDocumentUpload:
    """Service input for a multipart KB document upload."""

    filename: str
    content_type: str
    file: BinaryIO
    title: str | None = None
    metadata_tags: dict[str, Any] | None = None
    source_date: date | None = None
    is_official: bool = False
    priority: int = 0


def kb_document_to_response(document: KBDocument) -> KBDocumentResponse:
    """Map a KB document ORM object to a public DTO."""
    return KBDocumentResponse.model_validate(document)


def kb_event_to_response(event: KBDocumentEvent) -> KBDocumentEventResponse:
    """Map a KB document event ORM object to a public DTO."""
    return KBDocumentEventResponse(
        id=event.id,
        document_id=event.document_id,
        event_type=event.event_type,
        status=event.status,
        message=event.message,
        metadata=event.event_metadata,
        created_at=event.created_at,
    )


class KBDocumentService:
    """Admin KB document operations."""

    def __init__(
        self,
        session: AsyncSession,
        *,
        storage: StorageProvider,
        kb_provider: BaseKnowledgebaseProvider,
        document_repo: KBDocumentRepository | None = None,
        event_repo: KBDocumentEventRepository | None = None,
        audit_service: AuditLogService | None = None,
    ) -> None:
        self.session = session
        self.storage = storage
        self.kb_provider = kb_provider
        self.document_repo = document_repo or KBDocumentRepository(session)
        self.event_repo = event_repo or KBDocumentEventRepository(session)
        self.audit_service = audit_service or AuditLogService(session)

    async def list_documents(
        self,
        *,
        actor: User,
        processing_status: str | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> list[KBDocumentResponse]:
        """List organization KB documents."""
        rows = await self.document_repo.list_by_organization(
            actor.organization_id,
            processing_status=processing_status,
            limit=limit,
            offset=offset,
        )
        return [kb_document_to_response(row) for row in rows]

    async def get_document(
        self,
        *,
        actor: User,
        document_id: UUID,
    ) -> KBDocumentResponse:
        """Return one org-scoped KB document."""
        document = await self._get_document_or_404(actor, document_id)
        return kb_document_to_response(document)

    async def upload_document(
        self,
        *,
        actor: User,
        upload: KBDocumentUpload,
    ) -> KBDocumentResponse:
        """Store an original file and start KB ingestion."""
        self._validate_content_type(upload.filename, upload.content_type)
        size_bytes = self._size(upload.file)
        storage_key = kb_original_file_key(actor.organization_id, upload.filename)
        await self.storage.upload_file(storage_key, upload.file, upload.content_type)

        document = await self.document_repo.create(
            organization_id=actor.organization_id,
            uploaded_by=actor.id,
            title=upload.title or upload.filename,
            filename=upload.filename,
            content_type=upload.content_type,
            size_bytes=size_bytes,
            storage_key=storage_key,
            metadata_tags=upload.metadata_tags or {},
            source_date=upload.source_date,
            is_official=upload.is_official,
            priority=upload.priority,
        )
        await self.event_repo.create(
            document_id=document.id,
            event_type="document.uploaded",
            status=document.processing_status,
            message=None,
            metadata={"filename": document.filename},
        )
        signed_url = await self.storage.get_presigned_url(
            storage_key,
            download_filename=upload.filename,
        )
        ingest_response = await self.kb_provider.ingest_document(
            KBDocumentIngestRequest(
                playbook_document_id=document.id,
                source_uri=signed_url,
                filename=document.filename,
                content_type=document.content_type,
                size_bytes=document.size_bytes,
                source_title=document.title,
                source_date=document.source_date,
                is_official=document.is_official,
                priority=document.priority,
                visibility_policy=document.visibility_policy,
                metadata_tags=document.metadata_tags,
            )
        )
        await self.document_repo.link_kb_service_document(
            document,
            kb_service_document_id=ingest_response.kb_service_document_id,
        )
        await self.event_repo.create(
            document_id=document.id,
            event_type="ingestion.requested",
            status="uploaded",
            message=None,
            metadata={"task_id": ingest_response.task_id},
        )
        await self.audit_service.record(
            actor=actor,
            organization_id=actor.organization_id,
            action="kb.document_uploaded",
            target_type="kb_document",
            target_id=document.id,
            metadata={"filename": document.filename},
        )
        await self.session.commit()
        logger.info(
            "kb_document_uploaded",
            actor_user_id=str(actor.id),
            document_id=str(document.id),
            content_type=document.content_type,
            size_bytes=document.size_bytes,
        )
        return kb_document_to_response(document)

    async def update_metadata(
        self,
        *,
        actor: User,
        document_id: UUID,
        request: KBDocumentMetadataUpdateRequest,
    ) -> KBDocumentResponse:
        """Update KB document ranking/metadata fields."""
        document = await self._get_document_or_404(actor, document_id)
        previous = {
            "metadata_tags": document.metadata_tags,
            "source_date": document.source_date.isoformat()
            if document.source_date
            else None,
            "is_official": document.is_official,
            "priority": document.priority,
        }
        updated = await self.document_repo.update_metadata(
            document,
            metadata_tags=(
                request.metadata_tags
                if request.metadata_tags is not None
                else document.metadata_tags
            ),
            source_date=(
                request.source_date
                if request.source_date is not None
                else document.source_date
            ),
            is_official=(
                request.is_official
                if request.is_official is not None
                else document.is_official
            ),
            priority=request.priority if request.priority is not None else document.priority,
        )
        await self.event_repo.create(
            document_id=document.id,
            event_type="document.metadata_updated",
            status=document.processing_status,
            message=None,
            metadata={"previous": previous},
        )
        await self.audit_service.record(
            actor=actor,
            organization_id=actor.organization_id,
            action="kb.document_metadata_updated",
            target_type="kb_document",
            target_id=document.id,
            metadata={"previous": previous},
        )
        await self.session.commit()
        return kb_document_to_response(updated)

    async def retry_document(
        self,
        *,
        actor: User,
        document_id: UUID,
    ) -> KBDocumentResponse:
        """Retry ingestion by re-sending the original presigned URL to KB."""
        document = await self._get_document_or_404(actor, document_id)
        signed_url = await self.storage.get_presigned_url(
            document.storage_key,
            download_filename=document.filename,
        )
        ingest_response = await self.kb_provider.ingest_document(
            KBDocumentIngestRequest(
                playbook_document_id=document.id,
                source_uri=signed_url,
                filename=document.filename,
                content_type=document.content_type,
                size_bytes=document.size_bytes,
                source_title=document.title,
                source_date=document.source_date,
                is_official=document.is_official,
                priority=document.priority,
                visibility_policy=document.visibility_policy,
                metadata_tags=document.metadata_tags,
            )
        )
        await self.document_repo.update_status(
            document,
            processing_status="uploaded",
            failure_reason=None,
        )
        await self.document_repo.link_kb_service_document(
            document,
            kb_service_document_id=ingest_response.kb_service_document_id,
        )
        await self.event_repo.create(
            document_id=document.id,
            event_type="ingestion.retry_requested",
            status="uploaded",
            message=None,
            metadata={"task_id": ingest_response.task_id},
        )
        await self.audit_service.record(
            actor=actor,
            organization_id=actor.organization_id,
            action="kb.document_retry_requested",
            target_type="kb_document",
            target_id=document.id,
            metadata={},
        )
        await self.session.commit()
        return kb_document_to_response(document)

    async def delete_document(
        self,
        *,
        actor: User,
        document_id: UUID,
    ) -> None:
        """Delete a KB document and ask KB service to remove searchable vectors."""
        document = await self._get_document_or_404(actor, document_id)
        if document.kb_service_document_id is not None:
            await self.kb_provider.delete_document(str(document.kb_service_document_id))
        await self.storage.delete_file(document.storage_key)
        await self.audit_service.record(
            actor=actor,
            organization_id=actor.organization_id,
            action="kb.document_deleted",
            target_type="kb_document",
            target_id=document.id,
            metadata={"filename": document.filename},
        )
        await self.document_repo.delete(document)
        await self.session.commit()

    async def _get_document_or_404(
        self,
        actor: User,
        document_id: UUID,
    ) -> KBDocument:
        document = await self.document_repo.get_for_organization(
            organization_id=actor.organization_id,
            document_id=document_id,
        )
        if document is None:
            raise NotFoundError("KB document", str(document_id))
        return document

    @staticmethod
    def _validate_content_type(filename: str, content_type: str) -> None:
        if content_type not in SUPPORTED_KB_CONTENT_TYPES:
            raise UnsupportedFileTypeError(
                filename,
                content_type,
                sorted(SUPPORTED_KB_CONTENT_TYPES),
            )

    @staticmethod
    def _size(file: BinaryIO) -> int:
        position = file.tell()
        file.seek(0, 2)
        size = file.tell()
        file.seek(0)
        if position:
            file.seek(position)
        return size


class KBDocumentWebhookService:
    """Processes signed status callbacks from the KB service."""

    def __init__(
        self,
        session: AsyncSession,
        *,
        settings: Settings,
        document_repo: KBDocumentRepository | None = None,
        event_repo: KBDocumentEventRepository | None = None,
    ) -> None:
        self.session = session
        self.settings = settings
        self.document_repo = document_repo or KBDocumentRepository(session)
        self.event_repo = event_repo or KBDocumentEventRepository(session)

    async def process(
        self,
        *,
        payload: KBWebhookPayload,
        raw_body: bytes,
        signature: str | None,
    ) -> KBWebhookResponse:
        """Verify signature, update document status, and append an event."""
        self._verify_signature(raw_body=raw_body, signature=signature)
        self._verify_timestamp(payload.timestamp)

        document = await self.document_repo.get(payload.document_id)
        if document is None:
            document = await self.document_repo.get_by_kb_service_document_id(
                payload.document_id
            )
        if document is None:
            raise NotFoundError("KB document", str(payload.document_id))

        status = self._map_status(payload.status, payload.stage)
        await self.document_repo.update_status(
            document,
            processing_status=status,
            failure_reason=payload.error_message if status == "failed" else None,
        )
        await self.event_repo.create(
            document_id=document.id,
            event_type=f"kb.{payload.stage or 'pipeline'}.{payload.status.lower()}",
            status=status,
            message=payload.error_message,
            metadata={
                **payload.metadata,
                "raw_status": payload.status,
                "stage": payload.stage,
            },
            created_at=datetime.now(UTC),
        )
        await self.session.commit()
        logger.info(
            "kb_webhook_processed",
            document_id=str(document.id),
            status=status,
            stage=payload.stage,
        )
        return KBWebhookResponse(document_status=status)  # type: ignore[arg-type]

    def _verify_signature(self, *, raw_body: bytes, signature: str | None) -> None:
        if not self.settings.KB_WEBHOOK_SECRET:
            raise ForbiddenError("KB webhook secret is not configured")
        if not signature:
            raise ForbiddenError("Missing KB webhook signature")
        expected = hmac.new(
            self.settings.KB_WEBHOOK_SECRET.encode(),
            raw_body,
            hashlib.sha256,
        ).hexdigest()
        supplied = signature.removeprefix("sha256=")
        if not hmac.compare_digest(expected, supplied):
            raise ForbiddenError("Invalid KB webhook signature")

    @staticmethod
    def _verify_timestamp(timestamp: int | None) -> None:
        if timestamp is None:
            return
        if abs(int(time.time()) - timestamp) > 600:
            raise ForbiddenError("Stale KB webhook timestamp")

    @staticmethod
    def _map_status(raw_status: str, stage: str | None) -> str:
        status = raw_status.lower()
        normalized_stage = (stage or "").lower()
        if status in _TERMINAL_READY or (
            normalized_stage == "pipeline" and status == "success"
        ):
            return "ready"
        if status in _TERMINAL_FAILED or (
            normalized_stage == "pipeline" and status == "failed"
        ):
            return "failed"
        if status in _PROCESSING or status == "success":
            return "processing"
        if status == "pending":
            return "uploaded"
        return "processing"
