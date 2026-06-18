"""Conversation-file upload and ingest handoff workflows."""

from __future__ import annotations

from dataclasses import dataclass
from typing import BinaryIO
from uuid import UUID, uuid4

import structlog
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.core.error_codes import ErrorCode
from app.core.exceptions import AppError, NotFoundError, StorageError
from app.infrastructure.knowledgebase.providers.base import BaseKnowledgebaseProvider
from app.infrastructure.storage.paths import conversation_file_original_key
from app.infrastructure.storage.provider import StorageProvider
from app.models.identity import User
from app.repositories.conversations import (
    ConversationFileRepository,
    ConversationMessageRepository,
    ConversationRepository,
)
from app.repositories.uploads import KBIngestOutboxRepository, UploadRequestRepository
from app.schemas.conversations import (
    ConversationFileSummaryResponse,
    ConversationFileUploadRequest,
    ConversationFileUploadRequestResponse,
)
from app.schemas.knowledgebase import (
    KBConversationFileIngestRequest,
    KBDocumentIngestResponse,
)
from app.schemas.uploads import DirectUploadContract, UploadCompleteRequest
from app.services.conversations.mappers import conversation_file_response
from app.services.conversations.validation import validate_message_attachment
from app.services.direct_uploads import DirectUploadSourceRef, DirectUploadWorkflow
from app.services.upload_validation import (
    validate_conversation_content_type,
    validate_conversation_file_size,
    validate_conversation_filename,
    validate_declared_upload_size,
)
from app.workers.dispatcher import (
    KbIngestOutboxTaskDispatcher,
    UploadRequestReconciliationTaskDispatcher,
)

logger = structlog.get_logger(__name__)


@dataclass(frozen=True)
class ConversationFileUpload:
    """Service input for a multipart conversation-file upload."""

    filename: str
    content_type: str
    file: BinaryIO


class ConversationFileService:
    """Store conversation files and queue private KB ingest handoff."""

    def __init__(
        self,
        session: AsyncSession,
        *,
        conversation_repo: ConversationRepository,
        message_repo: ConversationMessageRepository,
        file_repo: ConversationFileRepository,
        upload_request_repo: UploadRequestRepository,
        outbox_repo: KBIngestOutboxRepository,
        outbox_dispatcher: KbIngestOutboxTaskDispatcher,
        upload_reconciliation_dispatcher: UploadRequestReconciliationTaskDispatcher,
        kb_provider: BaseKnowledgebaseProvider | None,
        storage: StorageProvider | None,
        settings: Settings | None,
    ) -> None:
        self.session = session
        self.conversation_repo = conversation_repo
        self.message_repo = message_repo
        self.file_repo = file_repo
        self.upload_request_repo = upload_request_repo
        self.outbox_repo = outbox_repo
        self.outbox_dispatcher = outbox_dispatcher
        self.upload_reconciliation_dispatcher = upload_reconciliation_dispatcher
        self.kb_provider = kb_provider
        self.storage = storage
        self.settings = settings
        self.upload_workflow = (
            DirectUploadWorkflow(
                storage=storage,
                upload_request_repo=upload_request_repo,
                outbox_repo=outbox_repo,
                outbox_dispatcher=outbox_dispatcher,
                upload_reconciliation_dispatcher=upload_reconciliation_dispatcher,
            )
            if storage is not None
            else None
        )

    async def upload_file(
        self,
        *,
        athlete: User,
        conversation_id: UUID,
        upload: ConversationFileUpload,
    ) -> ConversationFileSummaryResponse:
        """Store a conversation-scoped file original and queue private ingest intent."""
        conversation = await self._get_conversation_or_404(
            athlete=athlete,
            conversation_id=conversation_id,
        )
        storage = self._storage()

        filename = validate_conversation_filename(upload.filename)
        content_type = validate_conversation_content_type(
            filename,
            upload.content_type,
        )
        size_bytes = validate_conversation_file_size(
            filename,
            upload.file,
            max_size_bytes=self._max_upload_bytes(),
        )
        file_id = uuid4()
        storage_key = conversation_file_original_key(
            athlete.organization_id,
            conversation.id,
            file_id,
            filename,
        )

        try:
            upload.file.seek(0)
            await storage.upload_file(storage_key, upload.file, content_type)
            signed_url = await storage.get_presigned_url(
                storage_key,
                download_filename=filename,
            )
        except Exception as exc:
            logger.warning(
                "conversation_file_storage_failed",
                athlete_user_id=str(athlete.id),
                conversation_id=str(conversation.id),
                error_type=type(exc).__name__,
            )
            raise StorageError("Conversation file storage failed") from exc

        file = await self.file_repo.create(
            file_id=file_id,
            conversation_id=conversation.id,
            uploaded_by=athlete.id,
            filename=filename,
            content_type=content_type,
            size_bytes=size_bytes,
            storage_key=storage_key,
            extraction_status="uploaded",
        )
        ingest_request = KBConversationFileIngestRequest(
            organization_id=athlete.organization_id,
            conversation_id=conversation.id,
            conversation_file_id=file.id,
            source_uri=signed_url,
            filename=file.filename,
            content_type=file.content_type,
            size_bytes=file.size_bytes,
            source_title=file.filename,
        )
        try:
            if self.kb_provider is None:
                raise RuntimeError("Knowledgebase provider is not configured")
            ingest_response = await self.kb_provider.ingest_source(ingest_request)
            file = await self.file_repo.update_extraction_status(
                file,
                extraction_status="extracting",
                extraction_metadata=_conversation_file_ingest_metadata(
                    ingest_request,
                    ingest_response,
                ),
                error_message=None,
            )
            file = await self.file_repo.update_ingestion_mirror(
                file,
                kb_service_document_id=ingest_response.kb_service_document_id,
            )
        except Exception as exc:
            logger.warning(
                "conversation_file_ingest_dispatch_failed",
                athlete_user_id=str(athlete.id),
                conversation_id=str(conversation.id),
                conversation_file_id=str(file.id),
                error_type=type(exc).__name__,
            )
            file = await self.file_repo.update_extraction_status(
                file,
                extraction_status="failed",
                extraction_metadata=_conversation_file_ingest_failure_metadata(
                    ingest_request,
                    exc,
                ),
                error_message="KB ingestion dispatch failed",
            )
        await self.session.commit()
        logger.info(
            "conversation_file_uploaded",
            athlete_user_id=str(athlete.id),
            conversation_id=str(conversation.id),
            conversation_file_id=str(file.id),
            content_type=file.content_type,
            size_bytes=file.size_bytes,
        )
        return conversation_file_response(file, 0)

    async def create_file_upload_request(
        self,
        *,
        athlete: User,
        conversation_id: UUID,
        request: ConversationFileUploadRequest,
    ) -> ConversationFileUploadRequestResponse:
        """Create a direct-upload request for a conversation-scoped file."""
        conversation = await self._get_conversation_or_404(
            athlete=athlete,
            conversation_id=conversation_id,
        )
        self._storage()

        filename = validate_conversation_filename(request.filename)
        content_type = validate_conversation_content_type(
            filename,
            request.content_type,
        )
        validate_declared_upload_size(
            filename,
            request.size_bytes,
            max_size_bytes=self._max_upload_bytes(),
        )
        await validate_message_attachment(
            message_repo=self.message_repo,
            conversation_id=conversation.id,
            message_id=request.message_id,
        )

        file_id = uuid4()
        storage_key = conversation_file_original_key(
            athlete.organization_id,
            conversation.id,
            file_id,
            filename,
        )
        upload_workflow = self._direct_upload_workflow()
        presigned = await upload_workflow.create_presigned_post(
            storage_key=storage_key,
            content_type=content_type,
            size_bytes=request.size_bytes,
            error_message="Conversation file storage failed",
            log_event="conversation_file_presign_failed",
            log_context={
                "athlete_user_id": str(athlete.id),
                "conversation_id": str(conversation.id),
                "conversation_file_id": str(file_id),
            },
        )

        file = await self.file_repo.create(
            file_id=file_id,
            conversation_id=conversation.id,
            uploaded_by=athlete.id,
            filename=filename,
            content_type=content_type,
            size_bytes=request.size_bytes,
            storage_key=storage_key,
            message_id=request.message_id,
            extraction_status="upload_pending",
        )
        upload_request = await upload_workflow.record_upload_request(
            organization_id=athlete.organization_id,
            requested_by=athlete.id,
            source=DirectUploadSourceRef.conversation_file(file.id),
            filename=file.filename,
            content_type=file.content_type,
            size_bytes=file.size_bytes,
            storage_key=storage_key,
            expires_at=presigned.expires_at,
        )
        await self.session.commit()
        upload_workflow.dispatch_upload_reconciliation(
            expires_at=upload_request.expires_at,
            log_context={"conversation_file_id": str(file.id)},
        )
        logger.info(
            "conversation_file_upload_requested",
            athlete_user_id=str(athlete.id),
            conversation_id=str(conversation.id),
            conversation_file_id=str(file.id),
            content_type=file.content_type,
            size_bytes=file.size_bytes,
        )
        return ConversationFileUploadRequestResponse(
            file=conversation_file_response(file, 0),
            upload=DirectUploadContract(
                upload_request_id=upload_request.id,
                url=presigned.url,
                fields=presigned.fields,
                expires_at=presigned.expires_at,
            ),
        )

    async def complete_file_upload(
        self,
        *,
        athlete: User,
        conversation_id: UUID,
        file_id: UUID,
        request: UploadCompleteRequest,
    ) -> ConversationFileSummaryResponse:
        """Verify a direct conversation-file upload and queue private ingest."""
        conversation = await self._get_conversation_or_404(
            athlete=athlete,
            conversation_id=conversation_id,
        )
        self._storage()

        file = await self.file_repo.get_for_conversation(
            conversation_id=conversation.id,
            file_id=file_id,
        )
        if file is None:
            raise NotFoundError("Conversation file", str(file_id))

        upload_request = await self.upload_request_repo.get_for_conversation_file(
            upload_request_id=request.upload_request_id,
            conversation_file_id=file.id,
            for_update=True,
        )
        if upload_request is None:
            raise NotFoundError("Upload request", str(request.upload_request_id))

        upload_workflow = self._direct_upload_workflow()
        source = DirectUploadSourceRef.conversation_file(file.id)
        completion = await upload_workflow.complete_upload_request(upload_request)
        if completion.status == "already_completed":
            await upload_workflow.enqueue_ingest(
                organization_id=athlete.organization_id,
                source=source,
            )
            await self.session.commit()
            upload_workflow.dispatch_kb_ingest_outbox(
                log_context={"conversation_file_id": str(file.id)}
            )
            return conversation_file_response(file, file.chunk_count)

        file = await self.file_repo.update_extraction_status(
            file,
            extraction_status="uploaded",
            error_message=None,
        )
        await upload_workflow.enqueue_ingest(
            organization_id=athlete.organization_id,
            source=source,
        )
        await self.session.commit()
        upload_workflow.dispatch_kb_ingest_outbox(
            log_context={"conversation_file_id": str(file.id)}
        )
        logger.info(
            "conversation_file_upload_completed",
            athlete_user_id=str(athlete.id),
            conversation_id=str(conversation.id),
            conversation_file_id=str(file.id),
            content_type=file.content_type,
            size_bytes=file.size_bytes,
        )
        return conversation_file_response(file, file.chunk_count)

    async def _get_conversation_or_404(
        self,
        *,
        athlete: User,
        conversation_id: UUID,
    ):
        conversation = await self.conversation_repo.get_for_athlete(
            conversation_id=conversation_id,
            organization_id=athlete.organization_id,
            athlete_id=athlete.id,
        )
        if conversation is None:
            raise NotFoundError("Conversation", str(conversation_id))
        return conversation

    def _storage(self) -> StorageProvider:
        if self.storage is None:
            raise AppError(
                "Storage provider is not configured",
                ErrorCode.STORAGE_ERROR,
                retryable=True,
            )
        return self.storage

    def _max_upload_bytes(self) -> int:
        max_mb = (
            self.settings.CONVERSATION_FILE_MAX_UPLOAD_MB
            if self.settings is not None
            else 200
        )
        return max_mb * 1024 * 1024

    def _direct_upload_workflow(self) -> DirectUploadWorkflow:
        if self.upload_workflow is None:
            raise AppError(
                "Storage provider is not configured",
                ErrorCode.STORAGE_ERROR,
                retryable=True,
            )
        return self.upload_workflow


def _conversation_file_ingest_metadata(
    request: KBConversationFileIngestRequest,
    response: KBDocumentIngestResponse,
) -> dict[str, str | None]:
    return {
        "source_type": request.source_type,
        "conversation_id": str(request.conversation_id),
        "conversation_file_id": str(request.conversation_file_id),
        "kb_service_document_id": str(response.kb_service_document_id),
        "task_id": response.task_id,
        "kb_status": response.status,
    }


def _conversation_file_ingest_failure_metadata(
    request: KBConversationFileIngestRequest,
    exc: Exception,
) -> dict[str, str]:
    return {
        "source_type": request.source_type,
        "conversation_id": str(request.conversation_id),
        "conversation_file_id": str(request.conversation_file_id),
        "dispatch_error_type": type(exc).__name__,
    }
