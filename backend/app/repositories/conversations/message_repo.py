"""Repository for athlete conversation messages."""

from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

from fastapi import Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.infrastructure.db.session import get_db
from app.models.conversations import ConversationMessage
from app.repositories.conversations._sentinel import _UNSET, _UnsetType


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
