"""Athlete conversation service."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import timedelta
from typing import BinaryIO
from uuid import UUID, uuid4

import structlog
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.core.error_codes import ErrorCode
from app.core.exceptions import (
    AppError,
    NotFoundError,
    StorageError,
    ValidationError,
)
from app.infrastructure.knowledgebase.providers.base import BaseKnowledgebaseProvider
from app.infrastructure.storage.paths import conversation_file_original_key
from app.infrastructure.storage.provider import StorageProvider
from app.models.conversations import (
    ConversationFile,
    ConversationMessage,
    MessageCitation,
)
from app.models.identity import User
from app.repositories.conversations import (
    ConversationFileRepository,
    ConversationMessageRepository,
    ConversationRepository,
    MessageCitationRepository,
)
from app.repositories.uploads import KBIngestOutboxRepository, UploadRequestRepository
from app.schemas.conversations import (
    ConversationCreateRequest,
    ConversationDetailResponse,
    ConversationFileSummaryResponse,
    ConversationFileUploadRequest,
    ConversationFileUploadRequestResponse,
    ConversationMessageResponse,
    ConversationSummaryResponse,
    MessageCitationResponse,
    MessageSubmitRequest,
    MessageSubmitResponse,
)
from app.schemas.knowledgebase import (
    KBConversationFileIngestRequest,
    KBDocumentIngestResponse,
)
from app.schemas.uploads import DirectUploadContract, UploadCompleteRequest
from app.services.direct_uploads import DirectUploadSourceRef, DirectUploadWorkflow
from app.services.upload_validation import (
    validate_conversation_content_type,
    validate_conversation_file_size,
    validate_conversation_filename,
    validate_declared_upload_size,
)
from app.workers.dispatcher import (
    AthleteChatTaskDispatcher,
    AthleteChatTaskPayload,
    KbIngestOutboxTaskDispatcher,
    UploadRequestReconciliationTaskDispatcher,
)
from app.workers.queues import WorkerTaskName

logger = structlog.get_logger(__name__)

@dataclass(frozen=True)
class ConversationFileUpload:
    """Service input for a multipart conversation-file upload."""

    filename: str
    content_type: str
    file: BinaryIO


class ConversationService:
    """Minimal athlete-owned conversation operations."""

    def __init__(
        self,
        session: AsyncSession,
        *,
        conversation_repo: ConversationRepository | None = None,
        message_repo: ConversationMessageRepository | None = None,
        citation_repo: MessageCitationRepository | None = None,
        file_repo: ConversationFileRepository | None = None,
        upload_request_repo: UploadRequestRepository | None = None,
        outbox_repo: KBIngestOutboxRepository | None = None,
        athlete_chat_dispatcher: AthleteChatTaskDispatcher | None = None,
        outbox_dispatcher: KbIngestOutboxTaskDispatcher | None = None,
        upload_reconciliation_dispatcher: (
            UploadRequestReconciliationTaskDispatcher | None
        ) = None,
        kb_provider: BaseKnowledgebaseProvider | None = None,
        storage: StorageProvider | None = None,
        settings: Settings | None = None,
    ) -> None:
        self.session = session
        self.conversation_repo = conversation_repo or ConversationRepository(session)
        self.message_repo = message_repo or ConversationMessageRepository(session)
        self.citation_repo = citation_repo or MessageCitationRepository(session)
        self.file_repo = file_repo or ConversationFileRepository(session)
        self.upload_request_repo = upload_request_repo or UploadRequestRepository(
            session
        )
        self.outbox_repo = outbox_repo or KBIngestOutboxRepository(session)
        self.athlete_chat_dispatcher = (
            athlete_chat_dispatcher or AthleteChatTaskDispatcher()
        )
        self.outbox_dispatcher = outbox_dispatcher or KbIngestOutboxTaskDispatcher()
        self.upload_reconciliation_dispatcher = (
            upload_reconciliation_dispatcher
            or UploadRequestReconciliationTaskDispatcher()
        )
        self.kb_provider = kb_provider
        self.storage = storage
        self.settings = settings
        self.upload_workflow = (
            DirectUploadWorkflow(
                storage=storage,
                upload_request_repo=self.upload_request_repo,
                outbox_repo=self.outbox_repo,
                outbox_dispatcher=self.outbox_dispatcher,
                upload_reconciliation_dispatcher=self.upload_reconciliation_dispatcher,
            )
            if storage is not None
            else None
        )

    async def list_for_athlete(
        self,
        *,
        athlete: User,
        limit: int = 50,
        offset: int = 0,
    ) -> list[ConversationSummaryResponse]:
        """Return current athlete's conversations."""
        rows = await self.conversation_repo.list_for_athlete(
            organization_id=athlete.organization_id,
            athlete_id=athlete.id,
            limit=limit,
            offset=offset,
        )
        return [ConversationSummaryResponse.model_validate(row) for row in rows]

    async def create(
        self,
        *,
        athlete: User,
        request: ConversationCreateRequest,
    ) -> ConversationDetailResponse:
        """Create an athlete conversation seeded with the first user message."""
        conversation = await self.conversation_repo.create(
            organization_id=athlete.organization_id,
            athlete_id=athlete.id,
            title=None,
        )
        message = await self.message_repo.create(
            conversation_id=conversation.id,
            role="user",
            content=request.initial_message,
        )
        conversation = await self.conversation_repo.update_last_message_at(
            conversation,
            last_message_at=message.created_at,
        )
        await self.session.commit()
        return ConversationDetailResponse(
            **ConversationSummaryResponse.model_validate(conversation).model_dump(),
            messages=[await self._message_response(message)],
        )

    async def get_detail(
        self,
        *,
        athlete: User,
        conversation_id: UUID,
        message_limit: int = 100,
    ) -> ConversationDetailResponse:
        """Return one athlete-owned conversation with bounded messages."""
        conversation = await self.conversation_repo.get_for_athlete(
            conversation_id=conversation_id,
            organization_id=athlete.organization_id,
            athlete_id=athlete.id,
        )
        if conversation is None:
            raise NotFoundError("Conversation", str(conversation_id))

        messages = await self.message_repo.list_by_conversation(
            conversation.id,
            limit=message_limit,
        )
        citations_by_message = await self.citation_repo.list_by_messages(
            [message.id for message in messages],
        )
        files_with_counts = await self.file_repo.list_by_conversation_with_chunk_counts(
            conversation.id,
        )
        return ConversationDetailResponse(
            **ConversationSummaryResponse.model_validate(conversation).model_dump(),
            messages=[
                await self._message_response(
                    message,
                    citations=citations_by_message.get(message.id, []),
                )
                for message in messages
            ],
            files=[
                self._file_response(file, chunk_count)
                for file, chunk_count in files_with_counts
            ],
        )

    async def submit_message(
        self,
        *,
        athlete: User,
        conversation_id: UUID,
        request: MessageSubmitRequest,
    ) -> MessageSubmitResponse:
        """Persist a user turn, enqueue assistant work, and return stream metadata."""
        conversation = await self.conversation_repo.get_for_athlete(
            conversation_id=conversation_id,
            organization_id=athlete.organization_id,
            athlete_id=athlete.id,
        )
        if conversation is None:
            raise NotFoundError("Conversation", str(conversation_id))

        await self._validate_attached_files(
            conversation_id=conversation.id,
            file_ids=request.file_ids,
        )

        attached_file_ids = [str(file_id) for file_id in request.file_ids]
        task_id = str(uuid4())
        user_message = await self.message_repo.create(
            conversation_id=conversation.id,
            role="user",
            content=request.content,
            status="complete",
            metadata={"attached_file_ids": attached_file_ids},
        )
        assistant_message = await self.message_repo.create(
            conversation_id=conversation.id,
            role="assistant",
            content="",
            status="streaming",
            created_at=user_message.created_at + timedelta(microseconds=1),
            metadata={
                "task_id": task_id,
                "task_name": WorkerTaskName.RUN_ATHLETE_CHAT.value,
                "user_message_id": str(user_message.id),
            },
        )
        await self.conversation_repo.update_last_message_at(
            conversation,
            last_message_at=user_message.created_at,
        )
        await self.session.commit()

        try:
            self.athlete_chat_dispatcher.dispatch(
                task_id=task_id,
                payload=AthleteChatTaskPayload(
                    conversation_id=conversation.id,
                    athlete_user_id=athlete.id,
                    user_message_id=user_message.id,
                    assistant_message_id=assistant_message.id,
                    organization_id=athlete.organization_id,
                    attached_file_ids=request.file_ids,
                ),
            )
        except Exception as exc:
            await self.message_repo.update_status_and_content(
                assistant_message,
                status="failed",
                metadata={
                    **assistant_message.message_metadata,
                    "dispatch_error": type(exc).__name__,
                },
            )
            await self.session.commit()
            logger.error(
                "athlete_chat_task_dispatch_failed",
                conversation_id=str(conversation.id),
                assistant_message_id=str(assistant_message.id),
                task_id=task_id,
                error_type=type(exc).__name__,
                exc_info=True,
            )
            raise AppError(
                "Failed to enqueue athlete chat task",
                ErrorCode.AGENT_FAILED,
                retryable=True,
                details={
                    "conversation_id": str(conversation.id),
                    "assistant_message_id": str(assistant_message.id),
                },
            ) from exc

        return MessageSubmitResponse(
            user_message_id=user_message.id,
            assistant_message_id=assistant_message.id,
            task_id=task_id,
            stream_url=(
                f"/api/v1/conversations/{conversation.id}/messages/"
                f"{assistant_message.id}/stream?task_id={task_id}"
            ),
            status=assistant_message.status,
        )

    async def upload_file(
        self,
        *,
        athlete: User,
        conversation_id: UUID,
        upload: ConversationFileUpload,
    ) -> ConversationFileSummaryResponse:
        """Store a conversation-scoped file original and queue private ingest intent."""
        conversation = await self.conversation_repo.get_for_athlete(
            conversation_id=conversation_id,
            organization_id=athlete.organization_id,
            athlete_id=athlete.id,
        )
        if conversation is None:
            raise NotFoundError("Conversation", str(conversation_id))
        if self.storage is None:
            raise AppError(
                "Storage provider is not configured",
                ErrorCode.STORAGE_ERROR,
                retryable=True,
            )

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
            await self.storage.upload_file(storage_key, upload.file, content_type)
            signed_url = await self.storage.get_presigned_url(
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
                extraction_metadata=self._conversation_file_ingest_metadata(
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
                extraction_metadata=self._conversation_file_ingest_failure_metadata(
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
        return self._file_response(file, 0)

    async def create_file_upload_request(
        self,
        *,
        athlete: User,
        conversation_id: UUID,
        request: ConversationFileUploadRequest,
    ) -> ConversationFileUploadRequestResponse:
        """Create a direct-upload request for a conversation-scoped file."""
        conversation = await self.conversation_repo.get_for_athlete(
            conversation_id=conversation_id,
            organization_id=athlete.organization_id,
            athlete_id=athlete.id,
        )
        if conversation is None:
            raise NotFoundError("Conversation", str(conversation_id))
        if self.storage is None:
            raise AppError(
                "Storage provider is not configured",
                ErrorCode.STORAGE_ERROR,
                retryable=True,
            )

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
        await self._validate_message_attachment(
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
            file=self._file_response(file, 0),
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
        conversation = await self.conversation_repo.get_for_athlete(
            conversation_id=conversation_id,
            organization_id=athlete.organization_id,
            athlete_id=athlete.id,
        )
        if conversation is None:
            raise NotFoundError("Conversation", str(conversation_id))
        if self.storage is None:
            raise AppError(
                "Storage provider is not configured",
                ErrorCode.STORAGE_ERROR,
                retryable=True,
            )

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
            return self._file_response(file, file.chunk_count)

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
        return self._file_response(file, file.chunk_count)

    async def validate_message_stream(
        self,
        *,
        athlete: User,
        conversation_id: UUID,
        message_id: UUID,
        task_id: str,
    ) -> None:
        """Validate that an athlete can subscribe to one assistant message stream."""
        conversation = await self.conversation_repo.get_for_athlete(
            conversation_id=conversation_id,
            organization_id=athlete.organization_id,
            athlete_id=athlete.id,
        )
        if conversation is None:
            raise NotFoundError("Conversation", str(conversation_id))

        message = await self.message_repo.get(message_id)
        if (
            message is None
            or message.conversation_id != conversation.id
            or message.role != "assistant"
            or message.message_metadata.get("task_id") != task_id
        ):
            raise NotFoundError("Message stream", str(message_id))

    async def _validate_attached_files(
        self,
        *,
        conversation_id: UUID,
        file_ids: list[UUID],
    ) -> None:
        if not file_ids:
            return

        files = await self.file_repo.list_by_conversation_and_ids(
            conversation_id,
            file_ids,
        )
        if {file.id for file in files} != set(file_ids):
            raise ValidationError(
                "One or more file_ids are not available for this conversation"
            )

    async def _validate_message_attachment(
        self,
        *,
        conversation_id: UUID,
        message_id: UUID | None,
    ) -> None:
        if message_id is None:
            return
        message = await self.message_repo.get(message_id)
        if message is None or message.conversation_id != conversation_id:
            raise ValidationError("message_id is not available for this conversation")

    async def _message_response(
        self,
        message: ConversationMessage,
        *,
        citations: list[MessageCitation] | None = None,
    ) -> ConversationMessageResponse:
        if citations is None:
            citations = await self.citation_repo.list_by_message(message.id)
        return ConversationMessageResponse(
            id=message.id,
            conversation_id=message.conversation_id,
            role=message.role,
            content=message.content,
            status=message.status,
            safety_outcome=message.safety_outcome,
            topic_labels=message.topic_labels,
            risk_labels=message.risk_labels,
            metadata=message.message_metadata,
            citations=[self._citation_response(citation) for citation in citations],
            created_at=message.created_at,
        )

    @staticmethod
    def _citation_response(citation: MessageCitation) -> MessageCitationResponse:
        return MessageCitationResponse(
            id=citation.id,
            message_id=citation.message_id,
            document_id=citation.document_id,
            chunk_id=citation.chunk_id,
            source_title=citation.source_title,
            source_metadata=citation.source_metadata,
            rank=citation.rank,
            created_at=citation.created_at,
        )

    @staticmethod
    def _file_response(
        file: ConversationFile,
        chunk_count: int,
    ) -> ConversationFileSummaryResponse:
        return ConversationFileSummaryResponse(
            id=file.id,
            conversation_id=file.conversation_id,
            message_id=file.message_id,
            filename=file.filename,
            content_type=file.content_type,
            size_bytes=file.size_bytes,
            extraction_status=file.extraction_status,
            chunk_count=chunk_count,
            created_at=file.created_at,
            updated_at=file.updated_at,
        )

    @staticmethod
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

    @staticmethod
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
