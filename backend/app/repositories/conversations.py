"""Repositories for athlete conversations, messages, and citations."""

from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

from fastapi import Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.infrastructure.db.session import get_db
from app.models.conversations import Conversation, ConversationMessage, MessageCitation


class _UnsetType:
    """Sentinel type for omitted partial-update values."""


_UNSET = _UnsetType()


class ConversationRepository:
    """Data access for athlete-owned conversations."""

    def __init__(self, session: AsyncSession = Depends(get_db)) -> None:
        self.session = session

    async def get_for_athlete(
        self,
        *,
        conversation_id: UUID,
        organization_id: UUID,
        athlete_id: UUID,
    ) -> Conversation | None:
        """Return a conversation only if it belongs to the athlete."""
        result = await self.session.execute(
            select(Conversation).where(
                Conversation.id == conversation_id,
                Conversation.organization_id == organization_id,
                Conversation.athlete_id == athlete_id,
            )
        )
        return result.scalar_one_or_none()

    async def list_for_athlete(
        self,
        *,
        organization_id: UUID,
        athlete_id: UUID,
        status: str | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> list[Conversation]:
        """Return conversations for an athlete with deterministic ordering."""
        stmt = select(Conversation).where(
            Conversation.organization_id == organization_id,
            Conversation.athlete_id == athlete_id,
        )
        if status is not None:
            stmt = stmt.where(Conversation.status == status)

        result = await self.session.scalars(
            stmt.order_by(
                Conversation.last_message_at.desc().nulls_last(),
                Conversation.created_at.desc(),
                Conversation.id.asc(),
            )
            .limit(limit)
            .offset(offset)
        )
        return list(result.all())

    async def create(
        self,
        *,
        organization_id: UUID,
        athlete_id: UUID,
        title: str | None = None,
        status: str = "active",
    ) -> Conversation:
        """Create an athlete conversation without committing."""
        conversation = Conversation(
            organization_id=organization_id,
            athlete_id=athlete_id,
            title=title,
            status=status,
        )
        self.session.add(conversation)
        await self.session.flush()
        await self.session.refresh(conversation)
        return conversation

    async def update_last_message_at(
        self,
        conversation: Conversation,
        *,
        last_message_at: datetime,
    ) -> Conversation:
        """Update the conversation's last-message timestamp."""
        conversation.last_message_at = last_message_at
        await self.session.flush()
        await self.session.refresh(conversation)
        return conversation

    async def update_status(
        self,
        conversation: Conversation,
        *,
        status: str,
    ) -> Conversation:
        """Update conversation status without committing."""
        conversation.status = status
        await self.session.flush()
        await self.session.refresh(conversation)
        return conversation


class ConversationMessageRepository:
    """Data access for messages in athlete conversations."""

    def __init__(self, session: AsyncSession = Depends(get_db)) -> None:
        self.session = session

    async def get(self, message_id: UUID) -> ConversationMessage | None:
        """Return a message by ID."""
        result = await self.session.execute(
            select(ConversationMessage).where(ConversationMessage.id == message_id)
        )
        return result.scalar_one_or_none()

    async def create(
        self,
        *,
        conversation_id: UUID,
        role: str,
        content: str,
        status: str = "complete",
        safety_outcome: str | None = None,
        topic_labels: list[Any] | None = None,
        risk_labels: list[Any] | None = None,
        metadata: dict[str, Any] | None = None,
        created_at: datetime | None = None,
    ) -> ConversationMessage:
        """Append a conversation message without committing."""
        message = ConversationMessage(
            conversation_id=conversation_id,
            role=role,
            content=content,
            status=status,
            safety_outcome=safety_outcome,
        )
        if topic_labels is not None:
            message.topic_labels = topic_labels
        if risk_labels is not None:
            message.risk_labels = risk_labels
        if metadata is not None:
            message.message_metadata = metadata
        if created_at is not None:
            message.created_at = created_at

        self.session.add(message)
        await self.session.flush()
        await self.session.refresh(message)
        return message

    async def list_by_conversation(
        self,
        conversation_id: UUID,
        *,
        limit: int = 100,
        offset: int = 0,
    ) -> list[ConversationMessage]:
        """Return conversation messages in chronological order."""
        result = await self.session.scalars(
            select(ConversationMessage)
            .where(ConversationMessage.conversation_id == conversation_id)
            .order_by(
                ConversationMessage.created_at.asc(),
                ConversationMessage.id.asc(),
            )
            .limit(limit)
            .offset(offset)
        )
        return list(result.all())

    async def list_recent_for_conversation(
        self,
        conversation_id: UUID,
        *,
        limit: int,
    ) -> list[ConversationMessage]:
        """Return the newest bounded messages in chronological order."""
        result = await self.session.scalars(
            select(ConversationMessage)
            .where(ConversationMessage.conversation_id == conversation_id)
            .order_by(
                ConversationMessage.created_at.desc(),
                ConversationMessage.id.desc(),
            )
            .limit(limit)
        )
        return list(reversed(result.all()))

    async def update_status_and_content(
        self,
        message: ConversationMessage,
        *,
        status: str,
        content: str | _UnsetType = _UNSET,
        safety_outcome: str | None | _UnsetType = _UNSET,
        topic_labels: list[Any] | _UnsetType = _UNSET,
        risk_labels: list[Any] | _UnsetType = _UNSET,
        metadata: dict[str, Any] | _UnsetType = _UNSET,
    ) -> ConversationMessage:
        """Update assistant message persistence fields without committing."""
        message.status = status
        if not isinstance(content, _UnsetType):
            message.content = content
        if not isinstance(safety_outcome, _UnsetType):
            message.safety_outcome = safety_outcome
        if not isinstance(topic_labels, _UnsetType):
            message.topic_labels = topic_labels
        if not isinstance(risk_labels, _UnsetType):
            message.risk_labels = risk_labels
        if not isinstance(metadata, _UnsetType):
            message.message_metadata = metadata

        await self.session.flush()
        await self.session.refresh(message)
        return message


class MessageCitationRepository:
    """Data access for assistant message citations."""

    def __init__(self, session: AsyncSession = Depends(get_db)) -> None:
        self.session = session

    async def create(
        self,
        *,
        message_id: UUID,
        source_title: str,
        rank: int,
        document_id: UUID | None = None,
        chunk_id: UUID | None = None,
        source_metadata: dict[str, Any] | None = None,
    ) -> MessageCitation:
        """Append a source citation without committing."""
        citation = MessageCitation(
            message_id=message_id,
            document_id=document_id,
            chunk_id=chunk_id,
            source_title=source_title,
            rank=rank,
        )
        if source_metadata is not None:
            citation.source_metadata = source_metadata

        self.session.add(citation)
        await self.session.flush()
        await self.session.refresh(citation)
        return citation

    async def list_by_message(
        self,
        message_id: UUID,
        *,
        limit: int = 50,
        offset: int = 0,
    ) -> list[MessageCitation]:
        """Return citations for a message ordered by citation rank."""
        result = await self.session.scalars(
            select(MessageCitation)
            .where(MessageCitation.message_id == message_id)
            .order_by(
                MessageCitation.rank.asc(),
                MessageCitation.created_at.asc(),
                MessageCitation.id.asc(),
            )
            .limit(limit)
            .offset(offset)
        )
        return list(result.all())
