"""Repository for kb.documents CRUD."""
from __future__ import annotations

import uuid
from datetime import UTC, datetime

import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.document import Document

logger = structlog.get_logger(__name__)


class DocumentRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create(
        self,
        *,
        document_id: uuid.UUID,
        configuration_id: uuid.UUID,
        name: str,
        md5: str,
        s3_key: str,
        metadata: dict | None = None,
    ) -> Document:
        doc = Document(
            id=document_id,
            configuration_id=configuration_id,
            name=name,
            md5=md5,
            s3_key=s3_key,
            status="pending",
            metadata_=metadata or {},
        )
        self._session.add(doc)
        await self._session.commit()
        await self._session.refresh(doc)
        return doc

    async def get(self, document_id: uuid.UUID) -> Document | None:
        result = await self._session.execute(
            select(Document).where(Document.id == document_id)
        )
        return result.scalar_one_or_none()

    async def get_by_config_and_md5(
        self, configuration_id: uuid.UUID, md5: str
    ) -> Document | None:
        """Dedup lookup: a document is identified by (configuration_id, md5)."""
        result = await self._session.execute(
            select(Document).where(
                Document.configuration_id == configuration_id,
                Document.md5 == md5,
            )
        )
        return result.scalar_one_or_none()

    async def update_status(
        self,
        document_id: uuid.UUID,
        status: str,
        error_message: str | None = None,
    ) -> Document | None:
        doc = await self.get(document_id)
        if not doc:
            return None
        doc.status = status
        doc.updated_at = datetime.now(UTC)
        await self._session.commit()
        await self._session.refresh(doc)
        return doc

    async def update_summary(
        self,
        document_id: uuid.UUID,
        summary: str | None,
    ) -> Document | None:
        doc = await self.get(document_id)
        if not doc:
            return None
        doc.summary = summary
        doc.updated_at = datetime.now(UTC)
        await self._session.commit()
        await self._session.refresh(doc)
        return doc

    async def find_by_name(
        self,
        configuration_id: uuid.UUID,
        name: str,
    ) -> list[Document]:
        """Return all documents matching name within a configuration (usually 0 or 1)."""
        result = await self._session.execute(
            select(Document).where(
                Document.configuration_id == configuration_id,
                Document.name == name,
            )
        )
        return list(result.scalars().all())

    async def delete(self, document_id: uuid.UUID) -> bool:
        doc = await self.get(document_id)
        if not doc:
            return False
        await self._session.delete(doc)
        await self._session.commit()
        return True
