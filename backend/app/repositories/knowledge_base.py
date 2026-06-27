"""Repositories for backend-side knowledge base document records."""

from __future__ import annotations

from datetime import date, datetime
from typing import Any
from uuid import UUID

from fastapi import Depends
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.infrastructure.db.session import get_db
from app.models.knowledge_base import KBDocument, KBDocumentEvent


class _UnsetType:
    """Sentinel type for omitted partial-update values."""


_UNSET = _UnsetType()


class KBDocumentRepository:
    """Data access for admin-uploaded KB document metadata."""

    def __init__(self, session: AsyncSession = Depends(get_db)) -> None:
        self.session = session

    async def get(self, document_id: UUID) -> KBDocument | None:
        """Return a KB document by ID."""
        result = await self.session.execute(
            select(KBDocument).where(KBDocument.id == document_id)
        )
        return result.scalar_one_or_none()

    async def get_for_organization(
        self,
        *,
        organization_id: UUID,
        document_id: UUID,
    ) -> KBDocument | None:
        """Return a KB document scoped to an organization."""
        result = await self.session.execute(
            select(KBDocument).where(
                KBDocument.id == document_id,
                KBDocument.organization_id == organization_id,
            )
        )
        return result.scalar_one_or_none()

    async def get_by_kb_service_document_id(
        self,
        kb_service_document_id: UUID,
    ) -> KBDocument | None:
        """Return a KB document by its KB-service document ID."""
        result = await self.session.execute(
            select(KBDocument).where(
                KBDocument.kb_service_document_id == kb_service_document_id
            )
        )
        return result.scalar_one_or_none()

    async def list_by_organization(
        self,
        organization_id: UUID,
        *,
        processing_status: str | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> list[KBDocument]:
        """Return KB documents scoped to an organization."""
        stmt = select(KBDocument).where(KBDocument.organization_id == organization_id)
        if processing_status is not None:
            stmt = stmt.where(KBDocument.processing_status == processing_status)

        result = await self.session.scalars(
            stmt.order_by(KBDocument.created_at.desc(), KBDocument.id.asc())
            .limit(limit)
            .offset(offset)
        )
        return list(result.all())

    async def count_by_status(self, *, processing_status: str) -> int:
        """Return the number of KB documents in one processing status."""
        result = await self.session.scalar(
            select(func.count())
            .select_from(KBDocument)
            .where(KBDocument.processing_status == processing_status)
        )
        return int(result or 0)

    async def create(
        self,
        *,
        document_id: UUID | None = None,
        organization_id: UUID,
        uploaded_by: UUID,
        title: str,
        filename: str,
        content_type: str,
        size_bytes: int,
        storage_key: str,
        processing_status: str = "uploaded",
        visibility_policy: dict[str, Any] | None = None,
        metadata_tags: dict[str, Any] | None = None,
        source_date: date | None = None,
        is_official: bool = False,
        priority: int = 0,
    ) -> KBDocument:
        """Create a KB document metadata record without committing."""
        document = KBDocument(
            id=document_id,
            organization_id=organization_id,
            uploaded_by=uploaded_by,
            title=title,
            filename=filename,
            content_type=content_type,
            size_bytes=size_bytes,
            storage_key=storage_key,
            processing_status=processing_status,
            source_date=source_date,
            is_official=is_official,
            priority=priority,
        )
        if visibility_policy is not None:
            document.visibility_policy = visibility_policy
        if metadata_tags is not None:
            document.metadata_tags = metadata_tags

        self.session.add(document)
        await self.session.flush()
        await self.session.refresh(document)
        return document

    async def update_metadata(
        self,
        document: KBDocument,
        *,
        metadata_tags: dict[str, Any] | _UnsetType = _UNSET,
        visibility_policy: dict[str, Any] | _UnsetType = _UNSET,
        source_date: date | None | _UnsetType = _UNSET,
        is_official: bool | _UnsetType = _UNSET,
        priority: int | _UnsetType = _UNSET,
    ) -> KBDocument:
        """Update ranking and visibility metadata without committing."""
        if not isinstance(metadata_tags, _UnsetType):
            document.metadata_tags = metadata_tags
        if not isinstance(visibility_policy, _UnsetType):
            document.visibility_policy = visibility_policy
        if not isinstance(source_date, _UnsetType):
            document.source_date = source_date
        if not isinstance(is_official, _UnsetType):
            document.is_official = is_official
        if not isinstance(priority, _UnsetType):
            document.priority = priority

        await self.session.flush()
        await self.session.refresh(document)
        return document

    async def update_status(
        self,
        document: KBDocument,
        *,
        processing_status: str,
        failure_reason: str | None | _UnsetType = _UNSET,
    ) -> KBDocument:
        """Update document processing status without committing."""
        document.processing_status = processing_status
        if not isinstance(failure_reason, _UnsetType):
            document.failure_reason = failure_reason

        await self.session.flush()
        await self.session.refresh(document)
        return document

    async def update_ingestion_mirror(
        self,
        document: KBDocument,
        *,
        kb_service_document_id: UUID | None | _UnsetType = _UNSET,
        summary: str | None | _UnsetType = _UNSET,
        chunk_count: int | _UnsetType = _UNSET,
    ) -> KBDocument:
        """Update safe KB-service derived mirror metadata without committing."""
        if not isinstance(kb_service_document_id, _UnsetType):
            document.kb_service_document_id = kb_service_document_id
        if not isinstance(summary, _UnsetType):
            document.summary = summary
        if not isinstance(chunk_count, _UnsetType):
            document.chunk_count = chunk_count

        await self.session.flush()
        await self.session.refresh(document)
        return document

    async def link_kb_service_document(
        self,
        document: KBDocument,
        *,
        kb_service_document_id: UUID,
    ) -> KBDocument:
        """Persist the linked KB-service document ID without committing."""
        document.kb_service_document_id = kb_service_document_id
        await self.session.flush()
        await self.session.refresh(document)
        return document

    async def delete(self, document: KBDocument) -> None:
        """Delete a KB document metadata row without committing."""
        await self.session.delete(document)
        await self.session.flush()


class KBDocumentEventRepository:
    """Data access for KB document lifecycle events."""

    def __init__(self, session: AsyncSession = Depends(get_db)) -> None:
        self.session = session

    async def create(
        self,
        *,
        document_id: UUID,
        event_type: str,
        status: str | None,
        message: str | None,
        metadata: dict[str, Any],
        created_at: datetime | None = None,
    ) -> KBDocumentEvent:
        """Append a KB document lifecycle event without committing."""
        event = KBDocumentEvent(
            document_id=document_id,
            event_type=event_type,
            status=status,
            message=message,
            event_metadata=metadata,
        )
        if created_at is not None:
            event.created_at = created_at

        self.session.add(event)
        await self.session.flush()
        await self.session.refresh(event)
        return event

    async def list_by_document(
        self,
        document_id: UUID,
        *,
        limit: int = 100,
        offset: int = 0,
    ) -> list[KBDocumentEvent]:
        """Return lifecycle events for a KB document in chronological order."""
        result = await self.session.scalars(
            select(KBDocumentEvent)
            .where(KBDocumentEvent.document_id == document_id)
            .order_by(KBDocumentEvent.created_at.asc(), KBDocumentEvent.id.asc())
            .limit(limit)
            .offset(offset)
        )
        return list(result.all())
