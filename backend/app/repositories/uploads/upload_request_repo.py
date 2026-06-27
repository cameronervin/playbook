"""Repository for backend-owned direct-upload requests."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any
from uuid import UUID

from fastapi import Depends
from sqlalchemy import Select, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.infrastructure.db.session import get_db
from app.models.uploads import UploadRequest


class UploadRequestRepository:
    """Data access for backend-owned direct-upload requests."""

    def __init__(self, session: AsyncSession = Depends(get_db)) -> None:
        self.session = session

    async def create(
        self,
        *,
        organization_id: UUID,
        requested_by: UUID | None,
        source_type: str,
        filename: str,
        content_type: str,
        size_bytes: int,
        storage_key: str,
        expires_at: datetime,
        kb_document_id: UUID | None = None,
        conversation_file_id: UUID | None = None,
        status: str = "pending",
        request_metadata: dict[str, Any] | None = None,
    ) -> UploadRequest:
        """Create an upload request without committing."""
        request = UploadRequest(
            organization_id=organization_id,
            requested_by=requested_by,
            source_type=source_type,
            kb_document_id=kb_document_id,
            conversation_file_id=conversation_file_id,
            filename=filename,
            content_type=content_type,
            size_bytes=size_bytes,
            storage_key=storage_key,
            status=status,
            expires_at=expires_at,
        )
        if request_metadata is not None:
            request.request_metadata = request_metadata

        self.session.add(request)
        await self.session.flush()
        await self.session.refresh(request)
        return request

    async def get(self, upload_request_id: UUID) -> UploadRequest | None:
        """Return an upload request by ID."""
        result = await self.session.execute(
            select(UploadRequest).where(UploadRequest.id == upload_request_id)
        )
        return result.scalar_one_or_none()

    async def get_for_admin_document(
        self,
        *,
        upload_request_id: UUID,
        document_id: UUID,
        for_update: bool = False,
    ) -> UploadRequest | None:
        """Return an upload request scoped to one admin KB document."""
        result = await self.session.execute(
            self.admin_document_statement(
                upload_request_id=upload_request_id,
                document_id=document_id,
                for_update=for_update,
            )
        )
        return result.scalar_one_or_none()

    @classmethod
    def admin_document_statement(
        cls,
        *,
        upload_request_id: UUID,
        document_id: UUID,
        for_update: bool = False,
    ) -> Select[tuple[UploadRequest]]:
        """Build an admin-document upload request lookup statement."""
        stmt = select(UploadRequest).where(
            UploadRequest.id == upload_request_id,
            UploadRequest.source_type == "admin_upload",
            UploadRequest.kb_document_id == document_id,
        )
        if for_update:
            stmt = stmt.with_for_update()
        return stmt

    async def get_for_conversation_file(
        self,
        *,
        upload_request_id: UUID,
        conversation_file_id: UUID,
        for_update: bool = False,
    ) -> UploadRequest | None:
        """Return an upload request scoped to one conversation file."""
        result = await self.session.execute(
            self.conversation_file_statement(
                upload_request_id=upload_request_id,
                conversation_file_id=conversation_file_id,
                for_update=for_update,
            )
        )
        return result.scalar_one_or_none()

    @classmethod
    def conversation_file_statement(
        cls,
        *,
        upload_request_id: UUID,
        conversation_file_id: UUID,
        for_update: bool = False,
    ) -> Select[tuple[UploadRequest]]:
        """Build a conversation-file upload request lookup statement."""
        stmt = select(UploadRequest).where(
            UploadRequest.id == upload_request_id,
            UploadRequest.source_type == "conversation_file",
            UploadRequest.conversation_file_id == conversation_file_id,
        )
        if for_update:
            stmt = stmt.with_for_update()
        return stmt

    @classmethod
    def expired_pending_requests_statement(
        cls,
        *,
        now: datetime,
        limit: int,
        for_update: bool = False,
    ) -> Select[tuple[UploadRequest]]:
        """Build the expired pending direct-upload query."""
        stmt = (
            select(UploadRequest)
            .where(
                UploadRequest.status == "pending",
                UploadRequest.expires_at <= now,
            )
            .order_by(UploadRequest.expires_at.asc(), UploadRequest.id.asc())
            .limit(limit)
        )
        if for_update:
            stmt = stmt.with_for_update(skip_locked=True)
        return stmt

    async def list_expired_pending_requests(
        self,
        *,
        now: datetime,
        limit: int = 100,
        for_update: bool = False,
    ) -> list[UploadRequest]:
        """Return pending upload requests whose storage contracts have expired."""
        result = await self.session.scalars(
            self.expired_pending_requests_statement(
                now=now,
                limit=limit,
                for_update=for_update,
            )
        )
        return list(result.all())

    async def mark_completed(
        self,
        request: UploadRequest,
        *,
        completed_at: datetime | None = None,
    ) -> UploadRequest:
        """Mark an upload request completed without committing."""
        request.status = "completed"
        request.completed_at = completed_at or datetime.now(UTC)
        await self.session.flush()
        await self.session.refresh(request)
        return request

    async def mark_failed(
        self,
        request: UploadRequest,
        *,
        metadata: dict[str, Any] | None = None,
    ) -> UploadRequest:
        """Mark an upload request failed without committing."""
        request.status = "failed"
        if metadata is not None:
            request.request_metadata = metadata
        await self.session.flush()
        await self.session.refresh(request)
        return request

    async def mark_expired(
        self,
        request: UploadRequest,
        *,
        metadata: dict[str, Any] | None = None,
    ) -> UploadRequest:
        """Mark an upload request expired without committing."""
        request.status = "expired"
        if metadata is not None:
            request.request_metadata = metadata
        await self.session.flush()
        await self.session.refresh(request)
        return request

    async def next_pending_expiration_at(self) -> datetime | None:
        """Return the next pending upload request expiration timestamp."""
        return await self.session.scalar(
            select(func.min(UploadRequest.expires_at)).where(
                UploadRequest.status == "pending"
            )
        )
