"""Repository for athlete-owned conversations."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from fastapi import Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.infrastructure.db.session import get_db
from app.models.conversations import Conversation


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
