"""Athlete conversation service."""

from __future__ import annotations

from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import NotFoundError
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
)


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
    ) -> None:
        self.session = session
        self.conversation_repo = conversation_repo or ConversationRepository(session)
        self.message_repo = message_repo or ConversationMessageRepository(session)
        self.citation_repo = citation_repo or MessageCitationRepository(session)
        self.file_repo = file_repo or ConversationFileRepository(session)

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
