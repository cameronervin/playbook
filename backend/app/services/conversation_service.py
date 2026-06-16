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
    FileTooLargeError,
    NotFoundError,
    UnsupportedFileTypeError,
    ValidationError,
)
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
from app.schemas.conversations import (
    ConversationCreateRequest,
    ConversationDetailResponse,
    ConversationFileSummaryResponse,
    ConversationMessageResponse,
    ConversationSummaryResponse,
    MessageCitationResponse,
    MessageSubmitRequest,
    MessageSubmitResponse,
)
from app.schemas.knowledgebase import KBConversationFileIngestRequest
from app.services.conversation_file_ingest_dispatcher import (
    ConversationFileIngestDispatcher,
)
from app.workers.dispatcher import AthleteChatTaskDispatcher, AthleteChatTaskPayload
from app.workers.queues import WorkerTaskName

logger = structlog.get_logger(__name__)

SUPPORTED_CONVERSATION_FILE_TYPES = {
    ".pdf": "application/pdf",
    ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    ".pptx": "application/vnd.openxmlformats-officedocument.presentationml.presentation",
    ".xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
}


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
        athlete_chat_dispatcher: AthleteChatTaskDispatcher | None = None,
        conversation_file_ingest_dispatcher: ConversationFileIngestDispatcher | None = None,
        storage: StorageProvider | None = None,
        settings: Settings | None = None,
    ) -> None:
        self.session = session
        self.conversation_repo = conversation_repo or ConversationRepository(session)
        self.message_repo = message_repo or ConversationMessageRepository(session)
        self.citation_repo = citation_repo or MessageCitationRepository(session)
        self.file_repo = file_repo or ConversationFileRepository(session)
        self.athlete_chat_dispatcher = (
            athlete_chat_dispatcher or AthleteChatTaskDispatcher()
        )
        self.conversation_file_ingest_dispatcher = (
            conversation_file_ingest_dispatcher or ConversationFileIngestDispatcher()
        )
        self.storage = storage
        self.settings = settings

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

        filename = self._validate_filename(upload.filename)
        content_type = self._validate_content_type(filename, upload.content_type)
        size_bytes = self._validate_size(filename, upload.file)
        file_id = uuid4()
        storage_key = conversation_file_original_key(
            athlete.organization_id,
            conversation.id,
            file_id,
            filename,
        )

        upload.file.seek(0)
        await self.storage.upload_file(storage_key, upload.file, content_type)
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
        signed_url = await self.storage.get_presigned_url(
            storage_key,
            download_filename=filename,
        )
        await self.conversation_file_ingest_dispatcher.dispatch(
            KBConversationFileIngestRequest(
                organization_id=athlete.organization_id,
                conversation_id=conversation.id,
                conversation_file_id=file.id,
                source_uri=signed_url,
                filename=file.filename,
                content_type=file.content_type,
                size_bytes=file.size_bytes,
                source_title=file.filename,
            )
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
    def _validate_filename(filename: str) -> str:
        cleaned = filename.replace("\\", "/").rsplit("/", 1)[-1].strip()
        if not cleaned:
            raise ValidationError("Uploaded file must have a filename")
        if len(cleaned) > 500:
            raise ValidationError("Uploaded filename is too long")
        return cleaned

    @staticmethod
    def _validate_content_type(filename: str, content_type: str) -> str:
        lowered = filename.lower()
        extension = next(
            (
                supported_extension
                for supported_extension in SUPPORTED_CONVERSATION_FILE_TYPES
                if lowered.endswith(supported_extension)
            ),
            None,
        )
        allowed_types = sorted(SUPPORTED_CONVERSATION_FILE_TYPES.values())
        if extension is None:
            raise UnsupportedFileTypeError(filename, content_type, allowed_types)

        expected_content_type = SUPPORTED_CONVERSATION_FILE_TYPES[extension]
        if content_type != expected_content_type:
            raise UnsupportedFileTypeError(filename, content_type, allowed_types)
        return expected_content_type

    def _validate_size(self, filename: str, file: BinaryIO) -> int:
        position = file.tell()
        file.seek(0, 2)
        size = file.tell()
        file.seek(position)
        if size <= 0:
            raise ValidationError("Uploaded file must not be empty")

        max_size = self._max_upload_bytes()
        if size > max_size:
            raise FileTooLargeError(filename, size, max_size)
        return size

    def _max_upload_bytes(self) -> int:
        max_mb = (
            self.settings.CONVERSATION_FILE_MAX_UPLOAD_MB
            if self.settings is not None
            else 200
        )
        return max_mb * 1024 * 1024
