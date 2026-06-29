"""Repositories for admin analytics chat sessions and messages."""

from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

from fastapi import Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.infrastructure.db.session import get_db
from app.models.analytics import AdminChatMessage, AdminChatSession


class AdminChatSessionRepository:
    """Data access for admin chat sessions."""

    def __init__(self, session: AsyncSession = Depends(get_db)) -> None:
        self.session = session

    async def create(
        self,
        *,
        organization_id: UUID,
        created_by: UUID,
        title: str | None,
        context_window_start: datetime | None = None,
        context_window_end: datetime | None = None,
    ) -> AdminChatSession:
        """Create an admin chat session without committing."""
        row = AdminChatSession(
            organization_id=organization_id,
            created_by=created_by,
            title=title,
            context_window_start=context_window_start,
            context_window_end=context_window_end,
        )
        self.session.add(row)
        await self.session.flush()
        await self.session.refresh(row)
        return row

    async def get(self, session_id: UUID) -> AdminChatSession | None:
        """Return an admin chat session by ID."""
        result = await self.session.execute(
            select(AdminChatSession).where(AdminChatSession.id == session_id)
        )
        return result.scalar_one_or_none()

    async def get_for_admin(
        self,
        *,
        session_id: UUID,
        organization_id: UUID,
        admin_user_id: UUID,
    ) -> AdminChatSession | None:
        """Return one owner-scoped admin chat session."""
        result = await self.session.execute(
            select(AdminChatSession).where(
                AdminChatSession.id == session_id,
                AdminChatSession.organization_id == organization_id,
                AdminChatSession.created_by == admin_user_id,
            )
        )
        return result.scalar_one_or_none()

    async def list_for_admin(
        self,
        *,
        organization_id: UUID,
        admin_user_id: UUID,
        limit: int = 50,
        offset: int = 0,
    ) -> list[AdminChatSession]:
        """Return owner-scoped admin chat sessions ordered by recent activity."""
        result = await self.session.scalars(
            select(AdminChatSession)
            .where(
                AdminChatSession.organization_id == organization_id,
                AdminChatSession.created_by == admin_user_id,
            )
            .order_by(
                AdminChatSession.last_message_at.desc().nullslast(),
                AdminChatSession.created_at.desc(),
                AdminChatSession.id.asc(),
            )
            .limit(limit)
            .offset(offset)
        )
        return list(result.all())

    async def update_last_message_at(
        self,
        session: AdminChatSession,
        *,
        last_message_at: datetime,
    ) -> AdminChatSession:
        """Update a session activity timestamp without committing."""
        session.last_message_at = last_message_at
        await self.session.flush()
        await self.session.refresh(session)
        return session


class AdminChatMessageRepository:
    """Data access for admin chat messages."""

    def __init__(self, session: AsyncSession = Depends(get_db)) -> None:
        self.session = session

    async def create(
        self,
        *,
        session_id: UUID,
        role: str,
        content: str,
        status: str = "complete",
        references: list[dict[str, Any]] | None = None,
        metadata: dict[str, Any] | None = None,
        created_at: datetime | None = None,
    ) -> AdminChatMessage:
        """Create an admin chat message without committing."""
        row = AdminChatMessage(
            session_id=session_id,
            role=role,
            content=content,
            status=status,
        )
        if references is not None:
            row.references = references
        if metadata is not None:
            row.message_metadata = metadata
        if created_at is not None:
            row.created_at = created_at
        self.session.add(row)
        await self.session.flush()
        await self.session.refresh(row)
        return row

    async def get(self, message_id: UUID) -> AdminChatMessage | None:
        """Return an admin chat message by ID."""
        result = await self.session.execute(
            select(AdminChatMessage).where(AdminChatMessage.id == message_id)
        )
        return result.scalar_one_or_none()

    async def list_by_session(
        self,
        session_id: UUID,
        *,
        limit: int = 100,
        offset: int = 0,
    ) -> list[AdminChatMessage]:
        """Return messages for one admin chat session in chronological order."""
        result = await self.session.scalars(
            select(AdminChatMessage)
            .where(AdminChatMessage.session_id == session_id)
            .order_by(AdminChatMessage.created_at.asc(), AdminChatMessage.id.asc())
            .limit(limit)
            .offset(offset)
        )
        return list(result.all())

    async def list_recent_history(
        self,
        session_id: UUID,
        *,
        limit: int,
    ) -> list[AdminChatMessage]:
        """Return recent completed messages in chronological order."""
        result = await self.session.scalars(
            select(AdminChatMessage)
            .where(
                AdminChatMessage.session_id == session_id,
                AdminChatMessage.status == "complete",
            )
            .order_by(AdminChatMessage.created_at.desc(), AdminChatMessage.id.desc())
            .limit(limit)
        )
        return list(reversed(result.all()))

    async def update_status_content_references(
        self,
        message: AdminChatMessage,
        *,
        status: str,
        content: str | None = None,
        references: list[dict[str, Any]] | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> AdminChatMessage:
        """Update assistant placeholder status/content/references without committing."""
        message.status = status
        if content is not None:
            message.content = content
        if references is not None:
            message.references = references
        if metadata is not None:
            message.message_metadata = metadata
        await self.session.flush()
        await self.session.refresh(message)
        return message
