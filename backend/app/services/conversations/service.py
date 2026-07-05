"""Route-facing athlete conversation service facade."""

from __future__ import annotations

from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.infrastructure.knowledgebase.providers.base import BaseKnowledgebaseProvider
from app.infrastructure.storage.provider import StorageProvider
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
    ConversationStartResponse,
    ConversationSummaryResponse,
    MessageSubmitRequest,
    MessageSubmitResponse,
)
from app.schemas.uploads import UploadCompleteRequest
from app.services.conversations.file_service import (
    ConversationFileService,
    ConversationFileUpload,
)
from app.services.conversations.history_service import ConversationHistoryService
from app.services.conversations.message_service import ConversationMessageService
from app.workers.dispatcher import (
    AthleteChatTaskDispatcher,
    KbIngestOutboxTaskDispatcher,
    UploadRequestReconciliationTaskDispatcher,
)


class ConversationService:
    """Athlete-owned conversation operations facade."""

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

        self.history_service = ConversationHistoryService(
            session,
            conversation_repo=self.conversation_repo,
            message_repo=self.message_repo,
            citation_repo=self.citation_repo,
            file_repo=self.file_repo,
        )
        self.message_service = ConversationMessageService(
            session,
            conversation_repo=self.conversation_repo,
            message_repo=self.message_repo,
            file_repo=self.file_repo,
            athlete_chat_dispatcher=self.athlete_chat_dispatcher,
        )
        self.file_service = ConversationFileService(
            session,
            conversation_repo=self.conversation_repo,
            message_repo=self.message_repo,
            file_repo=self.file_repo,
            upload_request_repo=self.upload_request_repo,
            outbox_repo=self.outbox_repo,
            outbox_dispatcher=self.outbox_dispatcher,
            upload_reconciliation_dispatcher=self.upload_reconciliation_dispatcher,
            kb_provider=kb_provider,
            storage=storage,
            settings=settings,
        )
        self.upload_workflow = self.file_service.upload_workflow

    async def list_for_athlete(
        self,
        *,
        athlete: User,
        limit: int = 50,
        offset: int = 0,
    ) -> list[ConversationSummaryResponse]:
        """Return current athlete's conversations."""
        return await self.history_service.list_for_athlete(
            athlete=athlete,
            limit=limit,
            offset=offset,
        )

    async def create(
        self,
        *,
        athlete: User,
        request: ConversationCreateRequest,
    ) -> ConversationStartResponse:
        """Start an athlete conversation and enqueue assistant generation."""
        return await self.message_service.start_conversation(
            athlete=athlete,
            request=request,
        )

    async def get_detail(
        self,
        *,
        athlete: User,
        conversation_id: UUID,
        message_limit: int = 100,
    ) -> ConversationDetailResponse:
        """Return one athlete-owned conversation with bounded messages."""
        return await self.history_service.get_detail(
            athlete=athlete,
            conversation_id=conversation_id,
            message_limit=message_limit,
        )

    async def submit_message(
        self,
        *,
        athlete: User,
        conversation_id: UUID,
        request: MessageSubmitRequest,
    ) -> MessageSubmitResponse:
        """Persist a user turn, enqueue assistant work, and return stream metadata."""
        return await self.message_service.submit_message(
            athlete=athlete,
            conversation_id=conversation_id,
            request=request,
        )

    async def validate_message_stream(
        self,
        *,
        athlete: User,
        conversation_id: UUID,
        message_id: UUID,
        task_id: str,
    ) -> None:
        """Validate that an athlete can subscribe to one assistant message stream."""
        return await self.message_service.validate_message_stream(
            athlete=athlete,
            conversation_id=conversation_id,
            message_id=message_id,
            task_id=task_id,
        )

    async def upload_file(
        self,
        *,
        athlete: User,
        conversation_id: UUID,
        upload: ConversationFileUpload,
    ) -> ConversationFileSummaryResponse:
        """Store a conversation-scoped file original and queue private ingest intent."""
        return await self.file_service.upload_file(
            athlete=athlete,
            conversation_id=conversation_id,
            upload=upload,
        )

    async def create_file_upload_request(
        self,
        *,
        athlete: User,
        conversation_id: UUID,
        request: ConversationFileUploadRequest,
    ) -> ConversationFileUploadRequestResponse:
        """Create a direct-upload request for a conversation-scoped file."""
        return await self.file_service.create_file_upload_request(
            athlete=athlete,
            conversation_id=conversation_id,
            request=request,
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
        return await self.file_service.complete_file_upload(
            athlete=athlete,
            conversation_id=conversation_id,
            file_id=file_id,
            request=request,
        )
