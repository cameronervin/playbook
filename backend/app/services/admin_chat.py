"""Admin analytics chat service workflows."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from uuid import UUID, uuid4

import structlog
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings, get_settings
from app.core.error_codes import ErrorCode
from app.core.exceptions import AppError, NotFoundError
from app.models.analytics import AdminChatMessage, AdminChatSession
from app.models.identity import User
from app.repositories.admin_chat import (
    AdminChatMessageRepository,
    AdminChatSessionRepository,
)
from app.schemas.admin_chat import (
    AdminChatMessageResponse,
    AdminChatMessageSubmitRequest,
    AdminChatMessageSubmitResponse,
    AdminChatReference,
    AdminChatSessionCreateRequest,
    AdminChatSessionDetailResponse,
    AdminChatSessionResponse,
)
from app.services.admin_analytics import resolve_analytics_window
from app.services.audit_service import AuditLogService
from app.workers.dispatcher import AdminChatTaskDispatcher, AdminChatTaskPayload
from app.workers.queues import WorkerTaskName

logger = structlog.get_logger(__name__)


@dataclass(frozen=True, slots=True)
class _PersistedAdminChatTurn:
    """Persisted user/assistant turn plus stream metadata."""

    user_message: AdminChatMessage
    assistant_message: AdminChatMessage
    stream: AdminChatMessageSubmitResponse


class AdminChatService:
    """Coordinate admin analytics chat sessions, messages, and streams."""

    def __init__(
        self,
        session: AsyncSession,
        *,
        session_repo: AdminChatSessionRepository | None = None,
        message_repo: AdminChatMessageRepository | None = None,
        audit_service: AuditLogService | None = None,
        dispatcher: AdminChatTaskDispatcher | None = None,
        settings: Settings | None = None,
    ) -> None:
        self.session = session
        self.session_repo = session_repo or AdminChatSessionRepository(session)
        self.message_repo = message_repo or AdminChatMessageRepository(session)
        self.audit_service = audit_service or AuditLogService(session)
        self.dispatcher = dispatcher or AdminChatTaskDispatcher()
        self.settings = settings or get_settings()

    async def create_session(
        self,
        *,
        actor: User,
        request: AdminChatSessionCreateRequest,
    ) -> AdminChatSessionResponse:
        """Create an owner-scoped admin chat session."""
        context_window_start = request.context_window_start
        context_window_end = request.context_window_end
        if context_window_start is not None or context_window_end is not None:
            context_window_start, context_window_end = resolve_analytics_window(
                window=None,
                window_start=context_window_start,
                window_end=context_window_end,
                settings=self.settings,
            )

        row = await self.session_repo.create(
            organization_id=actor.organization_id,
            created_by=actor.id,
            title=_clean_title(request.title),
            context_window_start=context_window_start,
            context_window_end=context_window_end,
        )
        await self.audit_service.record(
            actor=actor,
            organization_id=actor.organization_id,
            action="admin_chat.session_created",
            target_type="admin_chat_session",
            target_id=row.id,
            metadata=_window_metadata(
                window_start=context_window_start,
                window_end=context_window_end,
            ),
        )
        await self.session.commit()
        return admin_chat_session_to_response(row)

    async def list_sessions(
        self,
        *,
        actor: User,
        limit: int,
        offset: int,
    ) -> list[AdminChatSessionResponse]:
        """List current admin's chat sessions."""
        rows = await self.session_repo.list_for_admin(
            organization_id=actor.organization_id,
            admin_user_id=actor.id,
            limit=limit,
            offset=offset,
        )
        return [admin_chat_session_to_response(row) for row in rows]

    async def get_session(
        self,
        *,
        actor: User,
        session_id: UUID,
        message_limit: int = 100,
    ) -> AdminChatSessionDetailResponse:
        """Return one owner-scoped admin chat session with messages."""
        row = await self.session_repo.get_for_admin(
            session_id=session_id,
            organization_id=actor.organization_id,
            admin_user_id=actor.id,
        )
        if row is None:
            raise NotFoundError("Admin chat session", str(session_id))
        messages = await self.message_repo.list_by_session(row.id, limit=message_limit)
        return admin_chat_session_detail_to_response(row, messages)

    async def submit_message(
        self,
        *,
        actor: User,
        session_id: UUID,
        request: AdminChatMessageSubmitRequest,
    ) -> AdminChatMessageSubmitResponse:
        """Persist an admin question and enqueue assistant generation."""
        row = await self.session_repo.get_for_admin(
            session_id=session_id,
            organization_id=actor.organization_id,
            admin_user_id=actor.id,
        )
        if row is None:
            raise NotFoundError("Admin chat session", str(session_id))

        window_start, window_end = _resolve_message_window(
            session=row,
            request=request,
            settings=self.settings,
        )
        turn = await self._persist_turn_and_dispatch(
            actor=actor,
            session=row,
            question=request.question,
            window_start=window_start,
            window_end=window_end,
        )
        return turn.stream

    async def validate_message_stream(
        self,
        *,
        actor: User,
        session_id: UUID,
        message_id: UUID,
        task_id: str,
    ) -> None:
        """Validate that an admin can subscribe to one assistant stream."""
        row = await self.session_repo.get_for_admin(
            session_id=session_id,
            organization_id=actor.organization_id,
            admin_user_id=actor.id,
        )
        if row is None:
            raise NotFoundError("Admin chat session", str(session_id))

        message = await self.message_repo.get(message_id)
        if (
            message is None
            or message.session_id != row.id
            or message.role != "assistant"
            or message.message_metadata.get("task_id") != task_id
        ):
            raise NotFoundError("Admin chat message stream", str(message_id))

    async def _persist_turn_and_dispatch(
        self,
        *,
        actor: User,
        session: AdminChatSession,
        question: str,
        window_start: datetime,
        window_end: datetime,
    ) -> _PersistedAdminChatTurn:
        """Persist one admin chat turn, enqueue work, and return stream metadata."""
        task_id = str(uuid4())
        window_metadata = _window_metadata(
            window_start=window_start,
            window_end=window_end,
        )
        user_message = await self.message_repo.create(
            session_id=session.id,
            role="user",
            content=question,
            status="complete",
            metadata=window_metadata,
        )
        assistant_message = await self.message_repo.create(
            session_id=session.id,
            role="assistant",
            content="",
            status="streaming",
            created_at=user_message.created_at + timedelta(microseconds=1),
            metadata={
                "task_id": task_id,
                "task_name": WorkerTaskName.RUN_ADMIN_CHAT.value,
                "user_message_id": str(user_message.id),
                **window_metadata,
            },
        )
        await self.session_repo.update_last_message_at(
            session,
            last_message_at=user_message.created_at,
        )
        await self.audit_service.record(
            actor=actor,
            organization_id=actor.organization_id,
            action="admin_chat.question_submitted",
            target_type="admin_chat_message",
            target_id=user_message.id,
            metadata={
                "session_id": str(session.id),
                "assistant_message_id": str(assistant_message.id),
                "task_id": task_id,
                **window_metadata,
            },
        )
        await self.session.commit()

        try:
            self.dispatcher.dispatch(
                task_id=task_id,
                payload=AdminChatTaskPayload(
                    session_id=session.id,
                    admin_user_id=actor.id,
                    user_message_id=user_message.id,
                    assistant_message_id=assistant_message.id,
                    organization_id=actor.organization_id,
                    window_start=window_start,
                    window_end=window_end,
                ),
            )
        except Exception as exc:
            await self.message_repo.update_status_content_references(
                assistant_message,
                status="failed",
                metadata={
                    **assistant_message.message_metadata,
                    "dispatch_error": type(exc).__name__,
                },
            )
            await self.session.commit()
            logger.error(
                "admin_chat_task_dispatch_failed",
                session_id=str(session.id),
                assistant_message_id=str(assistant_message.id),
                task_id=task_id,
                error_type=type(exc).__name__,
                exc_info=True,
            )
            raise AppError(
                "Failed to enqueue admin chat task",
                ErrorCode.AGENT_FAILED,
                retryable=True,
                details={
                    "session_id": str(session.id),
                    "assistant_message_id": str(assistant_message.id),
                },
            ) from exc

        return _PersistedAdminChatTurn(
            user_message=user_message,
            assistant_message=assistant_message,
            stream=AdminChatMessageSubmitResponse(
                session_id=session.id,
                user_message_id=user_message.id,
                assistant_message_id=assistant_message.id,
                task_id=task_id,
                stream_url=(
                    f"/api/v1/admin/chat/sessions/{session.id}/messages/"
                    f"{assistant_message.id}/stream?task_id={task_id}"
                ),
                status=assistant_message.status,
            ),
        )


def admin_chat_session_to_response(
    row: AdminChatSession,
) -> AdminChatSessionResponse:
    """Map an admin chat session ORM row to its public DTO."""
    return AdminChatSessionResponse(
        id=row.id,
        title=row.title,
        status=row.status,
        context_window_start=row.context_window_start,
        context_window_end=row.context_window_end,
        last_message_at=row.last_message_at,
        created_at=row.created_at,
        updated_at=row.updated_at,
    )


def admin_chat_message_to_response(
    row: AdminChatMessage,
) -> AdminChatMessageResponse:
    """Map an admin chat message ORM row to its public DTO."""
    metadata = dict(row.message_metadata or {})
    return AdminChatMessageResponse(
        id=row.id,
        session_id=row.session_id,
        role=row.role,
        content=row.content,
        status=row.status,
        references=[
            AdminChatReference(type=str(ref.get("type")), id=str(ref.get("id")))
            for ref in row.references
            if isinstance(ref, dict) and ref.get("type") and ref.get("id")
        ],
        metadata=metadata,
        answer_type=metadata.get("answer_type"),
        created_at=row.created_at,
    )


def admin_chat_session_detail_to_response(
    row: AdminChatSession,
    messages: list[AdminChatMessage],
) -> AdminChatSessionDetailResponse:
    """Map a session and messages to a detail DTO."""
    return AdminChatSessionDetailResponse(
        **admin_chat_session_to_response(row).model_dump(),
        messages=[admin_chat_message_to_response(message) for message in messages],
    )


def _resolve_message_window(
    *,
    session: AdminChatSession,
    request: AdminChatMessageSubmitRequest,
    settings: Settings,
) -> tuple[datetime, datetime]:
    if request.window_start is not None or request.window_end is not None:
        return resolve_analytics_window(
            window=None,
            window_start=request.window_start,
            window_end=request.window_end,
            settings=settings,
        )
    if request.window:
        return resolve_analytics_window(
            window=request.window,
            window_start=None,
            window_end=None,
            settings=settings,
        )
    if session.context_window_start is not None and session.context_window_end is not None:
        return resolve_analytics_window(
            window=None,
            window_start=session.context_window_start,
            window_end=session.context_window_end,
            settings=settings,
        )
    return resolve_analytics_window(
        window=None,
        window_start=None,
        window_end=None,
        settings=settings,
    )


def _clean_title(value: str | None) -> str | None:
    if value is None:
        return None
    cleaned = value.strip()
    return cleaned or None


def _window_metadata(
    *,
    window_start: datetime | None,
    window_end: datetime | None,
) -> dict[str, str]:
    metadata: dict[str, str] = {}
    if window_start is not None:
        metadata["window_start"] = window_start.isoformat()
    if window_end is not None:
        metadata["window_end"] = window_end.isoformat()
    return metadata
