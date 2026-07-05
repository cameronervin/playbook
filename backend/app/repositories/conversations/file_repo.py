"""Repository for athlete-uploaded conversation files."""

from __future__ import annotations

from typing import Any
from uuid import UUID

from fastapi import Depends
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.infrastructure.db.session import get_db
from app.models.conversations import Conversation, ConversationFile
from app.repositories.conversations._sentinel import _UNSET, _UnsetType


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

    async def get_with_conversation(
        self,
        file_id: UUID,
    ) -> tuple[ConversationFile, Conversation] | None:
        """Return one file with its owning conversation for trusted worker use."""
        result = await self.session.execute(
            select(ConversationFile, Conversation)
            .join(Conversation, ConversationFile.conversation_id == Conversation.id)
            .where(ConversationFile.id == file_id)
        )
        row = result.one_or_none()
        if row is None:
            return None
        return row[0], row[1]

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

    async def count_by_status(self, *, extraction_status: str) -> int:
        """Return the number of conversation files in one extraction status."""
        result = await self.session.scalar(
            select(func.count())
            .select_from(ConversationFile)
            .where(ConversationFile.extraction_status == extraction_status)
        )
        return int(result or 0)

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
