"""Admin-upload source handling for KB ingest outbox rows."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from app.infrastructure.storage.provider import StorageProvider
from app.models.knowledge_base import KBDocument
from app.models.uploads import KBIngestOutbox
from app.repositories.knowledge_base import (
    KBDocumentEventRepository,
    KBDocumentRepository,
)
from app.schemas.knowledgebase import KBDocumentIngestRequest, KBDocumentIngestResponse
from app.services.kb_ingest_outbox.failure_policy import (
    SAFE_FAILURE_REASON,
    OutboxResourceMismatchError,
    OutboxResourceMissingError,
)


class AdminUploadHandler:
    """Build and mirror admin-upload KB ingest work."""

    source_type = "admin_upload"

    def __init__(
        self,
        *,
        storage: StorageProvider,
        document_repo: KBDocumentRepository,
        document_event_repo: KBDocumentEventRepository,
    ) -> None:
        self.storage = storage
        self.document_repo = document_repo
        self.document_event_repo = document_event_repo

    async def load_resource(self, row: KBIngestOutbox) -> KBDocument:
        """Return the trusted backend document for this outbox row."""
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

    @staticmethod
    def linked_kb_service_document_id(
        row: KBIngestOutbox,
        resource: KBDocument,
    ) -> UUID | None:
        """Return an already-linked KB-service document ID if one exists."""
        return row.kb_service_document_id or resource.kb_service_document_id

    async def build_ingest_request(
        self,
        row: KBIngestOutbox,
        resource: KBDocument,
    ) -> KBDocumentIngestRequest:
        """Build a trusted KB-service ingest request from backend state."""
        if row.source_type != self.source_type:
            raise OutboxResourceMismatchError("Admin handler received non-admin row")
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

    async def mark_dispatched(
        self,
        row: KBIngestOutbox,
        resource: KBDocument,
        response: KBDocumentIngestResponse | None,
    ) -> None:
        """Mirror successful dispatch state to the admin document."""
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

    async def load_resource_for_failure(
        self,
        row: KBIngestOutbox,
    ) -> KBDocument | None:
        """Load the document for best-effort failure mirroring."""
        if row.kb_document_id is None:
            return None
        return await self.document_repo.get(row.kb_document_id)

    async def mark_retry_scheduled(
        self,
        row: KBIngestOutbox,
        resource: KBDocument | None,
        *,
        next_attempt_at: datetime,
        attempt_count: int,
        exc: Exception,
    ) -> None:
        """Append an admin document retry event."""
        if resource is None:
            return
        await self.document_event_repo.create(
            document_id=resource.id,
            event_type="ingestion.retry_scheduled",
            status=resource.processing_status,
            message=None,
            metadata={
                "outbox_id": str(row.id),
                "attempt_count": attempt_count,
                "next_attempt_at": next_attempt_at.isoformat(),
                "error_type": type(exc).__name__,
            },
        )

    async def mark_failed(
        self,
        row: KBIngestOutbox,
        resource: KBDocument | None,
        exc: Exception,
    ) -> None:
        """Mirror terminal failure state to the admin document."""
        if resource is None:
            return
        await self.document_repo.update_status(
            resource,
            processing_status="failed",
            failure_reason=SAFE_FAILURE_REASON,
        )
        await self.document_event_repo.create(
            document_id=resource.id,
            event_type="ingestion.failed",
            status="failed",
            message=SAFE_FAILURE_REASON,
            metadata={
                "outbox_id": str(row.id),
                "error_type": type(exc).__name__,
                "attempt_count": row.attempt_count,
            },
        )
