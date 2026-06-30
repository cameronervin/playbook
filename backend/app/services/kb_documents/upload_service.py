"""KB document upload workflows."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Any, BinaryIO
from uuid import UUID, uuid4

import structlog
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import NotFoundError
from app.infrastructure.knowledgebase import BaseKnowledgebaseProvider
from app.infrastructure.storage.paths import kb_original_file_key
from app.infrastructure.storage.provider import StorageProvider
from app.models.identity import User
from app.models.knowledge_base import KBDocument
from app.repositories.knowledge_base import (
    KBCollectionRepository,
    KBDocumentEventRepository,
    KBDocumentRepository,
    KBDocumentTagRepository,
    KBMetadataTagRepository,
)
from app.repositories.uploads import KBIngestOutboxRepository, UploadRequestRepository
from app.schemas.kb_documents import (
    KBDocumentResponse,
    KBDocumentUploadRequest,
    KBDocumentUploadRequestResponse,
)
from app.schemas.knowledgebase import KBDocumentIngestRequest
from app.schemas.uploads import DirectUploadContract, UploadCompleteRequest
from app.services.audit_service import AuditLogService
from app.services.direct_uploads import DirectUploadSourceRef, DirectUploadWorkflow
from app.services.kb_documents.catalog import KBCatalogService
from app.services.kb_documents.mappers import kb_document_to_response
from app.services.upload_validation import (
    file_size_bytes,
    validate_kb_content_type,
)
from app.workers.dispatcher import (
    KbIngestOutboxTaskDispatcher,
    UploadRequestReconciliationTaskDispatcher,
)

logger = structlog.get_logger(__name__)


@dataclass(frozen=True)
class KBDocumentUpload:
    """Service input for a multipart KB document upload."""

    filename: str
    content_type: str
    file: BinaryIO
    title: str | None = None
    metadata_tags: dict[str, Any] | None = None
    source_date: date | None = None
    collection_id: UUID | None = None
    tag_slugs: list[str] | None = None


class KBDocumentUploadService:
    """Admin KB upload and direct-upload completion workflows."""

    def __init__(
        self,
        session: AsyncSession,
        *,
        storage: StorageProvider,
        kb_provider: BaseKnowledgebaseProvider,
        document_repo: KBDocumentRepository,
        event_repo: KBDocumentEventRepository,
        collection_repo: KBCollectionRepository,
        tag_repo: KBMetadataTagRepository,
        document_tag_repo: KBDocumentTagRepository,
        upload_request_repo: UploadRequestRepository,
        outbox_repo: KBIngestOutboxRepository,
        outbox_dispatcher: KbIngestOutboxTaskDispatcher,
        upload_reconciliation_dispatcher: UploadRequestReconciliationTaskDispatcher,
        audit_service: AuditLogService,
    ) -> None:
        self.session = session
        self.storage = storage
        self.kb_provider = kb_provider
        self.document_repo = document_repo
        self.event_repo = event_repo
        self.catalog_service = KBCatalogService(
            session,
            collection_repo=collection_repo,
            tag_repo=tag_repo,
            document_tag_repo=document_tag_repo,
            audit_service=audit_service,
        )
        self.document_tag_repo = document_tag_repo
        self.upload_request_repo = upload_request_repo
        self.upload_workflow = DirectUploadWorkflow(
            storage=storage,
            upload_request_repo=upload_request_repo,
            outbox_repo=outbox_repo,
            outbox_dispatcher=outbox_dispatcher,
            upload_reconciliation_dispatcher=upload_reconciliation_dispatcher,
        )
        self.audit_service = audit_service

    async def upload_document(
        self,
        *,
        actor: User,
        upload: KBDocumentUpload,
    ) -> KBDocumentResponse:
        """Store an original file and start KB ingestion."""
        validate_kb_content_type(upload.filename, upload.content_type)
        size_bytes = file_size_bytes(upload.file)
        storage_key = kb_original_file_key(actor.organization_id, upload.filename)
        await self.storage.upload_file(storage_key, upload.file, upload.content_type)
        if upload.collection_id is None:
            raise NotFoundError("KB collection", "")
        resolved_metadata = await self.catalog_service.resolve_document_metadata(
            organization_id=actor.organization_id,
            collection_id=upload.collection_id,
            tag_slugs=upload.tag_slugs or [],
        )

        document = await self.document_repo.create(
            organization_id=actor.organization_id,
            uploaded_by=actor.id,
            title=upload.title or upload.filename,
            filename=upload.filename,
            content_type=upload.content_type,
            size_bytes=size_bytes,
            storage_key=storage_key,
            collection_id=resolved_metadata.collection.id,
            metadata_tags=resolved_metadata.metadata_tags,
            source_date=upload.source_date,
            is_official=True,
            priority=0,
        )
        await self.document_tag_repo.replace_tags(document, resolved_metadata.tags)
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
        validate_kb_content_type(request.filename, request.content_type)
        resolved_metadata = await self.catalog_service.resolve_document_metadata(
            organization_id=actor.organization_id,
            collection_id=request.collection_id,
            tag_slugs=request.tag_slugs,
        )

        document_id = uuid4()
        storage_key = kb_original_file_key(
            actor.organization_id,
            request.filename,
            document_id=document_id,
        )
        presigned = await self.upload_workflow.create_presigned_post(
            storage_key=storage_key,
            content_type=request.content_type,
            size_bytes=request.size_bytes,
            error_message="KB document upload request failed",
            log_event="kb_document_presign_failed",
            log_context={
                "actor_user_id": str(actor.id),
                "document_id": str(document_id),
            },
        )

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
            collection_id=resolved_metadata.collection.id,
            metadata_tags=resolved_metadata.metadata_tags,
            source_date=request.source_date,
            is_official=True,
            priority=0,
        )
        await self.document_tag_repo.replace_tags(document, resolved_metadata.tags)
        await self.event_repo.create(
            document_id=document.id,
            event_type="document.upload_requested",
            status=document.processing_status,
            message=None,
            metadata={"filename": document.filename},
        )
        upload_request = await self.upload_workflow.record_upload_request(
            organization_id=actor.organization_id,
            requested_by=actor.id,
            source=DirectUploadSourceRef.admin_document(document.id),
            filename=document.filename,
            content_type=document.content_type,
            size_bytes=document.size_bytes,
            storage_key=storage_key,
            expires_at=presigned.expires_at,
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
        self.upload_workflow.dispatch_upload_reconciliation(
            expires_at=upload_request.expires_at,
            log_context={"document_id": str(document.id)},
        )
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

        source = DirectUploadSourceRef.admin_document(document.id)
        completion = await self.upload_workflow.complete_upload_request(upload_request)
        if completion.status == "already_completed":
            await self.upload_workflow.enqueue_ingest(
                organization_id=document.organization_id,
                source=source,
            )
            await self.session.commit()
            self.upload_workflow.dispatch_kb_ingest_outbox(
                log_context={"document_id": str(document.id)}
            )
            return kb_document_to_response(document)

        document = await self.document_repo.update_status(
            document,
            processing_status="uploaded",
            failure_reason=None,
        )
        await self.upload_workflow.enqueue_ingest(
            organization_id=document.organization_id,
            source=source,
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
        self.upload_workflow.dispatch_kb_ingest_outbox(
            log_context={"document_id": str(document.id)}
        )
        logger.info(
            "kb_document_upload_completed",
            actor_user_id=str(actor.id),
            document_id=str(document.id),
            content_type=document.content_type,
            size_bytes=document.size_bytes,
        )
        return kb_document_to_response(document)

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
