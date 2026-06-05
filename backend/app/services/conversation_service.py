"""Athlete conversation shell service."""

from __future__ import annotations

from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import NotFoundError
from app.models.conversations import ConversationMessage, MessageCitation
from app.models.identity import User
from app.repositories.conversations import (
    ConversationMessageRepository,
    ConversationRepository,
    MessageCitationRepository,
)
from app.schemas.conversations import (
    ConversationCreateRequest,
    ConversationDetailResponse,
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
    ) -> None:
        self.session = session
        self.conversation_repo = conversation_repo or ConversationRepository(session)
        self.message_repo = message_repo or ConversationMessageRepository(session)
        self.citation_repo = citation_repo or MessageCitationRepository(session)

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
    ) -> ConversationSummaryResponse:
        """Create an athlete conversation shell."""
        row = await self.conversation_repo.create(
            organization_id=athlete.organization_id,
            athlete_id=athlete.id,
            title=request.title,
        )
        await self.session.commit()
        return ConversationSummaryResponse.model_validate(row)

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
        return ConversationDetailResponse(
            **ConversationSummaryResponse.model_validate(conversation).model_dump(),
            messages=[await self._message_response(message) for message in messages],
        )

    async def _message_response(
        self,
        message: ConversationMessage,
    ) -> ConversationMessageResponse:
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
