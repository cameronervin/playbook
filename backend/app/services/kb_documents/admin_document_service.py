"""Route-facing admin KB document service facade."""

from __future__ import annotations

from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.core.exceptions import NotFoundError, ValidationError
from app.infrastructure.knowledgebase import BaseKnowledgebaseProvider
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
    KBDocumentMetadataUpdateRequest,
    KBDocumentResponse,
    KBDocumentUploadRequest,
    KBDocumentUploadRequestResponse,
)
from app.schemas.uploads import UploadCompleteRequest
from app.services.audit_service import AuditLogService
from app.services.direct_uploads import DirectUploadSourceRef
from app.services.kb_documents.catalog import KBCatalogService
from app.services.kb_documents.mappers import kb_document_to_response
from app.services.kb_documents.upload_service import (
    KBDocumentUpload,
    KBDocumentUploadService,
)
from app.workers.dispatcher import (
    KbIngestOutboxTaskDispatcher,
    UploadRequestReconciliationTaskDispatcher,
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
        outbox_dispatcher: KbIngestOutboxTaskDispatcher | None = None,
        upload_reconciliation_dispatcher: (
            UploadRequestReconciliationTaskDispatcher | None
        ) = None,
        audit_service: AuditLogService | None = None,
        settings: Settings | None = None,
    ) -> None:
        self.session = session
        self.storage = storage
        self.kb_provider = kb_provider
        self.document_repo = document_repo or KBDocumentRepository(session)
        self.event_repo = event_repo or KBDocumentEventRepository(session)
        self.collection_repo = KBCollectionRepository(session)
        self.tag_repo = KBMetadataTagRepository(session)
        self.document_tag_repo = KBDocumentTagRepository(session)
        self.upload_request_repo = upload_request_repo or UploadRequestRepository(
            session
        )
        self.outbox_repo = outbox_repo or KBIngestOutboxRepository(session)
        self.outbox_dispatcher = outbox_dispatcher or KbIngestOutboxTaskDispatcher()
        self.upload_reconciliation_dispatcher = (
            upload_reconciliation_dispatcher
            or UploadRequestReconciliationTaskDispatcher()
        )
        self.audit_service = audit_service or AuditLogService(session)
        self.settings = settings
        self.catalog_service = KBCatalogService(
            session,
            collection_repo=self.collection_repo,
            tag_repo=self.tag_repo,
            document_tag_repo=self.document_tag_repo,
            audit_service=self.audit_service,
        )
        self.upload_service = KBDocumentUploadService(
            session,
            storage=storage,
            kb_provider=kb_provider,
            document_repo=self.document_repo,
            event_repo=self.event_repo,
            collection_repo=self.collection_repo,
            tag_repo=self.tag_repo,
            document_tag_repo=self.document_tag_repo,
            upload_request_repo=self.upload_request_repo,
            outbox_repo=self.outbox_repo,
            outbox_dispatcher=self.outbox_dispatcher,
            upload_reconciliation_dispatcher=self.upload_reconciliation_dispatcher,
            audit_service=self.audit_service,
        )
        self.upload_workflow = self.upload_service.upload_workflow

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
        return await self.upload_service.upload_document(actor=actor, upload=upload)

    async def create_upload_request(
        self,
        *,
        actor: User,
        request: KBDocumentUploadRequest,
    ) -> KBDocumentUploadRequestResponse:
        """Create a direct-upload request for an admin KB document."""
        return await self.upload_service.create_upload_request(
            actor=actor,
            request=request,
        )

    async def complete_upload(
        self,
        *,
        actor: User,
        document_id: UUID,
        request: UploadCompleteRequest,
    ) -> KBDocumentResponse:
        """Verify a direct upload and enqueue reliable KB ingest handoff."""
        return await self.upload_service.complete_upload(
            actor=actor,
            document_id=document_id,
            request=request,
        )

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
            "tag_slugs": [link.tag.slug for link in document.tag_links],
            "source_date": document.source_date.isoformat()
            if document.source_date
            else None,
        }
        metadata_tags = document.metadata_tags
        if request.tag_slugs is not None:
            if document.collection_id is None:
                raise ValidationError("Document is missing a KB collection")
            resolved_metadata = await self.catalog_service.resolve_document_metadata(
                organization_id=actor.organization_id,
                collection_id=document.collection_id,
                tag_slugs=request.tag_slugs,
                existing_metadata=document.metadata_tags,
                existing_document=document,
            )
            metadata_tags = resolved_metadata.metadata_tags
            await self.document_tag_repo.replace_tags(document, resolved_metadata.tags)

        source_date = document.source_date
        if "source_date" in request.model_fields_set:
            source_date = request.source_date

        updated = await self.document_repo.update_metadata(
            document,
            metadata_tags=metadata_tags,
            source_date=source_date,
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
            await self.upload_workflow.enqueue_ingest(
                organization_id=document.organization_id,
                source=DirectUploadSourceRef.admin_document(document.id),
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
        if ingest_response is None:
            self.upload_workflow.dispatch_kb_ingest_outbox(
                log_context={"document_id": str(document.id)}
            )
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
