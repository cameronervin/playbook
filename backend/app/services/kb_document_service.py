"""Knowledge-base document control-plane services."""

from __future__ import annotations

import hashlib
import hmac
import time
from dataclasses import dataclass
from datetime import UTC, date, datetime
from typing import Any, BinaryIO
from uuid import UUID, uuid4

import structlog
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.core.exceptions import (
    ForbiddenError,
    NotFoundError,
    StorageError,
    UnsupportedFileTypeError,
    ValidationError,
)
from app.core.log_redaction import redact_string
from app.infrastructure.knowledgebase import BaseKnowledgebaseProvider
from app.infrastructure.storage.paths import kb_original_file_key
from app.infrastructure.storage.provider import StorageProvider
from app.models.identity import User
from app.models.knowledge_base import KBDocument, KBDocumentEvent
from app.repositories.conversations import ConversationFileRepository
from app.repositories.knowledge_base import (
    KBDocumentEventRepository,
    KBDocumentRepository,
)
from app.repositories.uploads import KBIngestOutboxRepository, UploadRequestRepository
from app.schemas.kb_documents import (
    KBDocumentEventResponse,
    KBDocumentMetadataUpdateRequest,
    KBDocumentResponse,
    KBDocumentUploadRequest,
    KBDocumentUploadRequestResponse,
    KBWebhookPayload,
    KBWebhookResponse,
)
from app.schemas.knowledgebase import KBDocumentIngestRequest
from app.schemas.uploads import DirectUploadContract, UploadCompleteRequest
from app.services.audit_service import AuditLogService

logger = structlog.get_logger(__name__)

SUPPORTED_KB_CONTENT_TYPES = {
    "application/pdf",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "application/vnd.openxmlformats-officedocument.presentationml.presentation",
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
}

RESERVED_UPLOAD_METADATA_KEYS = {
    "source_type",
    "organization_id",
    "playbook_document_id",
    "conversation_id",
    "conversation_file_id",
    "kb_service_document_id",
    "source_uri",
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
        upload_request_repo: UploadRequestRepository | None = None,
        outbox_repo: KBIngestOutboxRepository | None = None,
        audit_service: AuditLogService | None = None,
        settings: Settings | None = None,
    ) -> None:
        self.session = session
        self.storage = storage
        self.kb_provider = kb_provider
        self.document_repo = document_repo or KBDocumentRepository(session)
        self.event_repo = event_repo or KBDocumentEventRepository(session)
        self.upload_request_repo = upload_request_repo or UploadRequestRepository(
            session
        )
        self.outbox_repo = outbox_repo or KBIngestOutboxRepository(session)
        self.audit_service = audit_service or AuditLogService(session)
        self.settings = settings

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
            is_official=True,
            priority=0,
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
                organization_id=actor.organization_id,
                playbook_document_id=document.id,
                source_uri=signed_url,
                filename=document.filename,
                content_type=document.content_type,
                size_bytes=document.size_bytes,
                source_title=document.title,
                source_date=document.source_date,
                is_official=True,
                priority=0,
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

    async def create_upload_request(
        self,
        *,
        actor: User,
        request: KBDocumentUploadRequest,
    ) -> KBDocumentUploadRequestResponse:
        """Create a direct-upload request for an admin KB document."""
        self._validate_content_type(request.filename, request.content_type)
        self._validate_metadata_tags(request.metadata_tags)

        document_id = uuid4()
        storage_key = kb_original_file_key(
            actor.organization_id,
            request.filename,
            document_id=document_id,
        )
        try:
            presigned = await self.storage.create_presigned_post(
                key=storage_key,
                content_type=request.content_type,
                max_size_bytes=request.size_bytes,
            )
        except Exception as exc:
            logger.warning(
                "kb_document_presign_failed",
                actor_user_id=str(actor.id),
                document_id=str(document_id),
                error_type=type(exc).__name__,
            )
            raise StorageError("KB document upload request failed") from exc

        document = await self.document_repo.create(
            document_id=document_id,
            organization_id=actor.organization_id,
            uploaded_by=actor.id,
            title=request.title or request.filename,
            filename=request.filename,
            content_type=request.content_type,
            size_bytes=request.size_bytes,
            storage_key=storage_key,
            processing_status="upload_pending",
            metadata_tags=request.metadata_tags,
            source_date=request.source_date,
            is_official=True,
            priority=0,
        )
        await self.event_repo.create(
            document_id=document.id,
            event_type="document.upload_requested",
            status=document.processing_status,
            message=None,
            metadata={"filename": document.filename},
        )
        upload_request = await self.upload_request_repo.create(
            organization_id=actor.organization_id,
            requested_by=actor.id,
            source_type="admin_upload",
            filename=document.filename,
            content_type=document.content_type,
            size_bytes=document.size_bytes,
            storage_key=storage_key,
            expires_at=presigned.expires_at,
            kb_document_id=document.id,
        )
        await self.audit_service.record(
            actor=actor,
            organization_id=actor.organization_id,
            action="kb.document_upload_requested",
            target_type="kb_document",
            target_id=document.id,
            metadata={"filename": document.filename},
        )
        await self.session.commit()
        logger.info(
            "kb_document_upload_requested",
            actor_user_id=str(actor.id),
            document_id=str(document.id),
            content_type=document.content_type,
            size_bytes=document.size_bytes,
        )
        return KBDocumentUploadRequestResponse(
            document=kb_document_to_response(document),
            upload=DirectUploadContract(
                upload_request_id=upload_request.id,
                url=presigned.url,
                fields=presigned.fields,
                expires_at=presigned.expires_at,
            ),
        )

    async def complete_upload(
        self,
        *,
        actor: User,
        document_id: UUID,
        request: UploadCompleteRequest,
    ) -> KBDocumentResponse:
        """Verify a direct upload and enqueue reliable KB ingest handoff."""
        document = await self._get_document_or_404(actor, document_id)
        upload_request = await self.upload_request_repo.get_for_admin_document(
            upload_request_id=request.upload_request_id,
            document_id=document.id,
            for_update=True,
        )
        if upload_request is None:
            raise NotFoundError("Upload request", str(request.upload_request_id))

        if upload_request.status == "completed":
            await self.outbox_repo.enqueue(
                organization_id=document.organization_id,
                source_type="admin_upload",
                kb_document_id=document.id,
            )
            await self.session.commit()
            return kb_document_to_response(document)

        self._validate_pending_upload_request(upload_request.expires_at)
        verification = await self.storage.verify_object(
            key=upload_request.storage_key,
            expected_size_bytes=upload_request.size_bytes,
            expected_content_type=upload_request.content_type,
        )
        self._raise_for_verification_failure(verification.status)

        await self.upload_request_repo.mark_completed(upload_request)
        document = await self.document_repo.update_status(
            document,
            processing_status="uploaded",
            failure_reason=None,
        )
        await self.outbox_repo.enqueue(
            organization_id=document.organization_id,
            source_type="admin_upload",
            kb_document_id=document.id,
        )
        await self.event_repo.create(
            document_id=document.id,
            event_type="document.uploaded",
            status=document.processing_status,
            message=None,
            metadata={"filename": document.filename},
        )
        await self.event_repo.create(
            document_id=document.id,
            event_type="ingestion.queued",
            status=document.processing_status,
            message=None,
            metadata={},
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
            "kb_document_upload_completed",
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
        """Update KB document metadata fields."""
        document = await self._get_document_or_404(actor, document_id)
        previous = {
            "metadata_tags": document.metadata_tags,
            "source_date": document.source_date.isoformat()
            if document.source_date
            else None,
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
        if document.kb_service_document_id is not None:
            ingest_response = await self.kb_provider.retry_document(
                str(document.kb_service_document_id)
            )
        else:
            if document.processing_status == "upload_pending":
                raise ValidationError("Document upload is not complete")
            await self.outbox_repo.enqueue(
                organization_id=document.organization_id,
                source_type="admin_upload",
                kb_document_id=document.id,
            )
            ingest_response = None
        await self.document_repo.update_status(
            document,
            processing_status="uploaded",
            failure_reason=None,
        )
        if ingest_response is not None:
            await self.document_repo.link_kb_service_document(
                document,
                kb_service_document_id=ingest_response.kb_service_document_id,
            )
        await self.event_repo.create(
            document_id=document.id,
            event_type="ingestion.retry_requested",
            status="uploaded",
            message=None,
            metadata=(
                {"task_id": ingest_response.task_id}
                if ingest_response is not None
                else {"queued": True}
            ),
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
    def _validate_metadata_tags(metadata_tags: dict[str, Any]) -> None:
        reserved = sorted(set(metadata_tags).intersection(RESERVED_UPLOAD_METADATA_KEYS))
        if reserved:
            raise ValidationError(
                f"metadata_tags contains reserved keys: {', '.join(reserved)}"
            )

    @staticmethod
    def _validate_pending_upload_request(expires_at: datetime) -> None:
        if expires_at <= datetime.now(UTC):
            raise ValidationError("Upload request has expired")

    @staticmethod
    def _raise_for_verification_failure(status: str) -> None:
        if status == "valid":
            return
        if status == "missing":
            raise ValidationError("Uploaded object is missing")
        raise ValidationError("Uploaded object does not match request metadata")

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
        file_repo: ConversationFileRepository | None = None,
    ) -> None:
        self.session = session
        self.settings = settings
        self.document_repo = document_repo or KBDocumentRepository(session)
        self.event_repo = event_repo or KBDocumentEventRepository(session)
        self.file_repo = file_repo or ConversationFileRepository(session)

    async def process(
        self,
        *,
        payload: KBWebhookPayload,
        raw_body: bytes,
        signature: str | None,
    ) -> KBWebhookResponse:
        """Verify signature, route status by source type, and mirror safe metadata."""
        self._verify_signature(raw_body=raw_body, signature=signature)
        self._verify_timestamp(payload.timestamp)

        if payload.source_type == "conversation_file":
            return await self._process_conversation_file(payload)
        return await self._process_admin_upload(payload)

    async def _process_admin_upload(
        self,
        payload: KBWebhookPayload,
    ) -> KBWebhookResponse:
        """Mirror a KB-service webhook into an admin KB document row."""
        document = await self._resolve_admin_document(payload)
        status = self._map_status(payload.status, payload.stage)
        failure_reason = (
            self._sanitize_failure_reason(payload.error_message)
            if status == "failed"
            else None
        )
        await self.document_repo.update_status(
            document,
            processing_status=status,
            failure_reason=failure_reason,
        )
        mirror_update: dict[str, Any] = {}
        kb_service_document_id = self._admin_kb_service_document_id(payload)
        if kb_service_document_id is not None:
            mirror_update["kb_service_document_id"] = kb_service_document_id
        if payload.summary is not None:
            mirror_update["summary"] = payload.summary
        chunk_count = self._chunk_count_from_metadata(payload.metadata)
        if chunk_count is not None:
            mirror_update["chunk_count"] = chunk_count
        if mirror_update:
            await self.document_repo.update_ingestion_mirror(
                document,
                **mirror_update,
            )
        await self.event_repo.create(
            document_id=document.id,
            event_type=f"kb.{payload.stage or 'pipeline'}.{payload.status.lower()}",
            status=status,
            message=failure_reason,
            metadata={
                **payload.metadata,
                "raw_status": payload.status,
                "stage": payload.stage,
                "source_type": payload.source_type or "admin_upload",
                "kb_service_document_id": self._document_kb_service_document_id(
                    document
                ),
            },
            created_at=datetime.now(UTC),
        )
        await self.session.commit()
        logger.info(
            "kb_webhook_processed",
            source_type=payload.source_type or "admin_upload",
            document_id=str(document.id),
            status=status,
            stage=payload.stage,
        )
        return KBWebhookResponse(document_status=status)  # type: ignore[arg-type]

    async def _process_conversation_file(
        self,
        payload: KBWebhookPayload,
    ) -> KBWebhookResponse:
        """Mirror a KB-service webhook into a conversation file row."""
        if payload.conversation_id is None or payload.conversation_file_id is None:
            raise NotFoundError("Conversation file", str(payload.document_id))

        file = await self.file_repo.get_for_conversation(
            conversation_id=payload.conversation_id,
            file_id=payload.conversation_file_id,
        )
        if file is None:
            kb_service_document_id = payload.kb_service_document_id or payload.document_id
            file = await self.file_repo.get_by_kb_service_document_id(
                kb_service_document_id
            )
            if file is None or file.conversation_id != payload.conversation_id:
                raise NotFoundError(
                    "Conversation file",
                    str(payload.conversation_file_id),
                )

        status = self._map_status(payload.status, payload.stage)
        file_status = "extracting" if status == "processing" else status
        failure_reason = (
            self._sanitize_failure_reason(payload.error_message)
            if status == "failed"
            else None
        )
        await self.file_repo.update_extraction_status(
            file,
            extraction_status=file_status,
            error_message=failure_reason,
        )
        mirror_update: dict[str, Any] = {
            "kb_service_document_id": payload.kb_service_document_id
            or payload.document_id
        }
        if payload.summary is not None:
            mirror_update["summary"] = payload.summary
        chunk_count = self._chunk_count_from_metadata(payload.metadata)
        if chunk_count is not None:
            mirror_update["chunk_count"] = chunk_count
        await self.file_repo.update_ingestion_mirror(file, **mirror_update)
        await self.session.commit()
        logger.info(
            "kb_webhook_processed",
            source_type="conversation_file",
            conversation_id=str(file.conversation_id),
            conversation_file_id=str(file.id),
            status=file_status,
            stage=payload.stage,
        )
        return KBWebhookResponse(document_status=status)  # type: ignore[arg-type]

    async def _resolve_admin_document(self, payload: KBWebhookPayload) -> KBDocument:
        if payload.playbook_document_id is not None:
            document = await self.document_repo.get(payload.playbook_document_id)
            if document is not None:
                return document

        document = await self.document_repo.get(payload.document_id)
        if document is None:
            document = await self.document_repo.get_by_kb_service_document_id(
                payload.document_id
            )
        if document is None:
            raise NotFoundError("KB document", str(payload.document_id))
        return document

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

    @staticmethod
    def _chunk_count_from_metadata(metadata: dict[str, Any]) -> int | None:
        raw_count = metadata.get("chunk_count")
        if isinstance(raw_count, bool) or not isinstance(raw_count, int):
            return None
        if raw_count < 0:
            return None
        return raw_count

    @staticmethod
    def _admin_kb_service_document_id(payload: KBWebhookPayload) -> UUID | None:
        if payload.kb_service_document_id is not None:
            return payload.kb_service_document_id
        if (
            payload.source_type == "admin_upload"
            and payload.playbook_document_id is not None
        ):
            return payload.document_id
        return None

    @staticmethod
    def _document_kb_service_document_id(document: KBDocument) -> str | None:
        kb_service_document_id = getattr(document, "kb_service_document_id", None)
        return str(kb_service_document_id) if kb_service_document_id else None

    @staticmethod
    def _sanitize_failure_reason(message: str | None) -> str | None:
        if message is None:
            return None
        redacted = redact_string(message)
        if "http://" in redacted or "https://" in redacted:
            return "KB ingestion failed"
        return redacted[:500]
