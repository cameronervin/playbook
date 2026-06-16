"""Repositories for athlete conversations, messages, and citations."""

from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

from fastapi import Depends
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.infrastructure.db.session import get_db
from app.models.conversations import (
    Conversation,
    ConversationFile,
    ConversationMessage,
    MessageCitation,
)


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


class ConversationFileRepository:
    """Data access for athlete-uploaded conversation files."""

    def __init__(self, session: AsyncSession = Depends(get_db)) -> None:
        self.session = session

    async def create(
        self,
        *,
        file_id: UUID | None = None,
        conversation_id: UUID,
        uploaded_by: UUID,
        filename: str,
        content_type: str,
        size_bytes: int,
        storage_key: str,
        message_id: UUID | None = None,
        extraction_status: str = "uploaded",
        extracted_text_ref: str | None = None,
        extracted_text_sha256: str | None = None,
        extracted_char_count: int | None = None,
        extraction_metadata: dict[str, Any] | None = None,
        error_message: str | None = None,
    ) -> ConversationFile:
        """Create conversation file metadata without committing."""
        file = ConversationFile(
            id=file_id,
            conversation_id=conversation_id,
            message_id=message_id,
            uploaded_by=uploaded_by,
            filename=filename,
            content_type=content_type,
            size_bytes=size_bytes,
            storage_key=storage_key,
            extraction_status=extraction_status,
            extracted_text_ref=extracted_text_ref,
            extracted_text_sha256=extracted_text_sha256,
            extracted_char_count=extracted_char_count,
            error_message=error_message,
        )
        if extraction_metadata is not None:
            file.extraction_metadata = extraction_metadata

        self.session.add(file)
        await self.session.flush()
        await self.session.refresh(file)
        return file

    async def list_by_conversation_with_chunk_counts(
        self,
        conversation_id: UUID,
        *,
        limit: int = 100,
        offset: int = 0,
    ) -> list[tuple[ConversationFile, int]]:
        """Return conversation files with mirrored KB-service chunk counts."""
        result = await self.session.scalars(
            select(ConversationFile)
            .where(ConversationFile.conversation_id == conversation_id)
            .order_by(ConversationFile.created_at.asc(), ConversationFile.id.asc())
            .limit(limit)
            .offset(offset)
        )
        return [(file, file.chunk_count) for file in result.all()]

    async def get_for_conversation(
        self,
        *,
        conversation_id: UUID,
        file_id: UUID,
    ) -> ConversationFile | None:
        """Return one file only when it belongs to the expected conversation."""
        result = await self.session.execute(
            select(ConversationFile).where(
                ConversationFile.id == file_id,
                ConversationFile.conversation_id == conversation_id,
            )
        )
        return result.scalar_one_or_none()

    async def get_by_kb_service_document_id(
        self,
        kb_service_document_id: UUID,
    ) -> ConversationFile | None:
        """Return a conversation file by its KB-service document ID."""
        result = await self.session.execute(
            select(ConversationFile).where(
                ConversationFile.kb_service_document_id == kb_service_document_id
            )
        )
        return result.scalar_one_or_none()

    async def list_by_conversation_and_ids(
        self,
        conversation_id: UUID,
        file_ids: list[UUID],
    ) -> list[ConversationFile]:
        """Return files matching IDs only when scoped to the conversation."""
        if not file_ids:
            return []

        result = await self.session.scalars(
            select(ConversationFile)
            .where(
                ConversationFile.conversation_id == conversation_id,
                ConversationFile.id.in_(file_ids),
            )
            .order_by(ConversationFile.created_at.asc(), ConversationFile.id.asc())
        )
        return list(result.all())

    async def list_ready_by_conversation(
        self,
        conversation_id: UUID,
    ) -> list[ConversationFile]:
        """Return ready files with mirrored chunks for one conversation."""
        result = await self.session.scalars(
            select(ConversationFile)
            .where(
                ConversationFile.conversation_id == conversation_id,
                ConversationFile.extraction_status == "ready",
                ConversationFile.chunk_count > 0,
            )
            .order_by(ConversationFile.created_at.asc(), ConversationFile.id.asc())
        )
        return list(result.all())

    async def list_ready_by_conversation_and_ids(
        self,
        conversation_id: UUID,
        file_ids: list[UUID],
    ) -> list[ConversationFile]:
        """Return ready requested files scoped to one conversation."""
        if not file_ids:
            return []

        result = await self.session.scalars(
            select(ConversationFile)
            .where(
                ConversationFile.conversation_id == conversation_id,
                ConversationFile.id.in_(file_ids),
                ConversationFile.extraction_status == "ready",
                ConversationFile.chunk_count > 0,
            )
            .order_by(ConversationFile.created_at.asc(), ConversationFile.id.asc())
        )
        return list(result.all())

    async def update_extraction_status(
        self,
        file: ConversationFile,
        *,
        extraction_status: str,
        extracted_text_ref: str | None | _UnsetType = _UNSET,
        extracted_text_sha256: str | None | _UnsetType = _UNSET,
        extracted_char_count: int | None | _UnsetType = _UNSET,
        extraction_metadata: dict[str, Any] | _UnsetType = _UNSET,
        error_message: str | None | _UnsetType = _UNSET,
    ) -> ConversationFile:
        """Update extraction lifecycle metadata without committing."""
        file.extraction_status = extraction_status
        if not isinstance(extracted_text_ref, _UnsetType):
            file.extracted_text_ref = extracted_text_ref
        if not isinstance(extracted_text_sha256, _UnsetType):
            file.extracted_text_sha256 = extracted_text_sha256
        if not isinstance(extracted_char_count, _UnsetType):
            file.extracted_char_count = extracted_char_count
        if not isinstance(extraction_metadata, _UnsetType):
            file.extraction_metadata = extraction_metadata
        if not isinstance(error_message, _UnsetType):
            file.error_message = error_message

        await self.session.flush()
        await self.session.refresh(file)
        return file

    async def update_ingestion_mirror(
        self,
        file: ConversationFile,
        *,
        kb_service_document_id: UUID | None | _UnsetType = _UNSET,
        summary: str | None | _UnsetType = _UNSET,
        chunk_count: int | _UnsetType = _UNSET,
    ) -> ConversationFile:
        """Update safe KB-service derived mirror metadata without committing."""
        if not isinstance(kb_service_document_id, _UnsetType):
            file.kb_service_document_id = kb_service_document_id
        if not isinstance(summary, _UnsetType):
            file.summary = summary
        if not isinstance(chunk_count, _UnsetType):
            file.chunk_count = chunk_count

        await self.session.flush()
        await self.session.refresh(file)
        return file
