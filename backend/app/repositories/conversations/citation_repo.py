"""Repository for assistant message citations."""

from __future__ import annotations

from typing import Any
from uuid import UUID

from fastapi import Depends
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.infrastructure.db.session import get_db
from app.models.conversations import MessageCitation


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

    async def list_by_messages(
        self,
        message_ids: list[UUID],
    ) -> dict[UUID, list[MessageCitation]]:
        """Return citations for messages keyed by message ID."""
        if not message_ids:
            return {}

        citations_by_message = {message_id: [] for message_id in message_ids}
        result = await self.session.scalars(
            select(MessageCitation)
            .where(MessageCitation.message_id.in_(message_ids))
            .order_by(
                MessageCitation.message_id.asc(),
                MessageCitation.rank.asc(),
                MessageCitation.created_at.asc(),
                MessageCitation.id.asc(),
            )
        )
        for citation in result.all():
            citations_by_message[citation.message_id].append(citation)
        return citations_by_message

    async def delete_by_message(self, message_id: UUID) -> None:
        """Delete citations for a message without committing."""
        await self.session.execute(
            delete(MessageCitation).where(MessageCitation.message_id == message_id)
        )
        await self.session.flush()
