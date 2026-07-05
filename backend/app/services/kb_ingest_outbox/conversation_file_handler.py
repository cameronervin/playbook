"""Conversation-file source handling for KB ingest outbox rows."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from app.infrastructure.storage.provider import StorageProvider
from app.models.conversations import Conversation, ConversationFile
from app.models.uploads import KBIngestOutbox
from app.repositories.conversations import ConversationFileRepository
from app.schemas.knowledgebase import (
    KBConversationFileIngestRequest,
    KBDocumentIngestResponse,
)
from app.services.kb_ingest_outbox.failure_policy import (
    SAFE_FAILURE_REASON,
    OutboxResourceMismatchError,
    OutboxResourceMissingError,
)

ConversationFileResource = tuple[ConversationFile, Conversation]


class ConversationFileHandler:
    """Build and mirror conversation-file KB ingest work."""

    source_type = "conversation_file"

    def __init__(
        self,
        *,
        storage: StorageProvider,
        file_repo: ConversationFileRepository,
    ) -> None:
        self.storage = storage
        self.file_repo = file_repo

    async def load_resource(self, row: KBIngestOutbox) -> ConversationFileResource:
        """Return the trusted backend file and owning conversation."""
        if row.conversation_file_id is None:
            raise OutboxResourceMissingError("Outbox row has no conversation file")
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

    @staticmethod
    def linked_kb_service_document_id(
        row: KBIngestOutbox,
        resource: ConversationFileResource,
    ) -> UUID | None:
        """Return an already-linked KB-service document ID if one exists."""
        file, _conversation = resource
        return row.kb_service_document_id or file.kb_service_document_id

    async def build_ingest_request(
        self,
        row: KBIngestOutbox,
        resource: ConversationFileResource,
    ) -> KBConversationFileIngestRequest:
        """Build a trusted private-ingest request from backend state."""
        if row.source_type != self.source_type:
            raise OutboxResourceMismatchError(
                "Conversation handler received non-file row"
            )
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

    async def mark_dispatched(
        self,
        row: KBIngestOutbox,
        resource: ConversationFileResource,
        response: KBDocumentIngestResponse | None,
    ) -> None:
        """Mirror successful dispatch state to the conversation file."""
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
                "extracting"
                if file.extraction_status == "uploaded"
                else file.extraction_status
            ),
            extraction_metadata=extraction_metadata,
            error_message=None,
        )

    async def load_resource_for_failure(
        self,
        row: KBIngestOutbox,
    ) -> ConversationFileResource | None:
        """Load the file for best-effort failure mirroring."""
        if row.conversation_file_id is None:
            return None
        return await self.file_repo.get_with_conversation(row.conversation_file_id)

    async def mark_retry_scheduled(
        self,
        row: KBIngestOutbox,
        resource: ConversationFileResource | None,
        *,
        next_attempt_at: datetime,
        attempt_count: int,
        exc: Exception,
    ) -> None:
        """Conversation-file retry does not change athlete-visible state."""

    async def mark_failed(
        self,
        row: KBIngestOutbox,
        resource: ConversationFileResource | None,
        exc: Exception,
    ) -> None:
        """Mirror terminal failure state to the conversation file."""
        if resource is None:
            return
        file, _conversation = resource
        await self.file_repo.update_extraction_status(
            file,
            extraction_status="failed",
            extraction_metadata={
                "source_type": "conversation_file",
                "conversation_file_id": str(file.id),
                "dispatch_error_type": type(exc).__name__,
            },
            error_message=SAFE_FAILURE_REASON,
        )
