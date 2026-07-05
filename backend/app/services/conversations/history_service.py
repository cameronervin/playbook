"""Conversation history workflows for athlete-owned conversations."""

from __future__ import annotations

from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import NotFoundError
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
    ConversationSummaryResponse,
)
from app.services.conversations.mappers import (
    conversation_detail_response,
    conversation_file_response,
    conversation_message_response,
    conversation_summary_response,
)


class ConversationHistoryService:
    """Read and create athlete-owned conversation history."""

    def __init__(
        self,
        session: AsyncSession,
        *,
        conversation_repo: ConversationRepository,
        message_repo: ConversationMessageRepository,
        citation_repo: MessageCitationRepository,
        file_repo: ConversationFileRepository,
    ) -> None:
        self.session = session
        self.conversation_repo = conversation_repo
        self.message_repo = message_repo
        self.citation_repo = citation_repo
        self.file_repo = file_repo

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
        return [conversation_summary_response(row) for row in rows]

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
            content=request.content,
        )
        conversation = await self.conversation_repo.update_last_message_at(
            conversation,
            last_message_at=message.created_at,
        )
        await self.session.commit()
        return conversation_detail_response(
            conversation,
            messages=[conversation_message_response(message, citations=[])],
            files=[],
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
        return conversation_detail_response(
            conversation,
            messages=[
                conversation_message_response(
                    message,
                    citations=citations_by_message.get(message.id, []),
                )
                for message in messages
            ],
            files=[
                conversation_file_response(file, chunk_count)
                for file, chunk_count in files_with_counts
            ],
        )
