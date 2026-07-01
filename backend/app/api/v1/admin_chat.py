"""Admin analytics chat routes."""

from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Header, Query, Request, status
from fastapi.responses import StreamingResponse

from app.api.v1.dependencies import (
    AdminChatServiceDep,
    AdminUserDep,
    AgentStreamServiceDep,
    RateLimitServiceDep,
)
from app.core.exceptions import ValidationError
from app.schemas.admin_chat import (
    AdminChatMessageSubmitRequest,
    AdminChatMessageSubmitResponse,
    AdminChatSessionCreateRequest,
    AdminChatSessionDetailResponse,
    AdminChatSessionResponse,
)
from app.services.agent_stream_service import AgentStreamService, format_sse_record
from app.services.rate_limit import RateLimitPolicy

router = APIRouter(prefix="/admin/chat", tags=["Admin Chat"])


@router.get("/sessions", response_model=list[AdminChatSessionResponse])
async def list_admin_chat_sessions(
    http_request: Request,
    admin: AdminUserDep,
    service: AdminChatServiceDep,
    rate_limiter: RateLimitServiceDep,
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> list[AdminChatSessionResponse]:
    """List current admin's analytics chat sessions."""
    await rate_limiter.enforce(
        RateLimitPolicy.LIST,
        request=http_request,
        user=admin,
    )
    return await service.list_sessions(actor=admin, limit=limit, offset=offset)


@router.post(
    "/sessions",
    response_model=AdminChatSessionResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_admin_chat_session(
    payload: AdminChatSessionCreateRequest,
    http_request: Request,
    admin: AdminUserDep,
    service: AdminChatServiceDep,
    rate_limiter: RateLimitServiceDep,
) -> AdminChatSessionResponse:
    """Create an admin analytics chat session."""
    await rate_limiter.enforce(
        RateLimitPolicy.ADMIN_CHAT,
        request=http_request,
        user=admin,
    )
    return await service.create_session(actor=admin, request=payload)


@router.get(
    "/sessions/{session_id}",
    response_model=AdminChatSessionDetailResponse,
)
async def get_admin_chat_session(
    session_id: UUID,
    admin: AdminUserDep,
    service: AdminChatServiceDep,
    message_limit: Annotated[int, Query(ge=1, le=500)] = 100,
) -> AdminChatSessionDetailResponse:
    """Get an admin analytics chat session with messages."""
    return await service.get_session(
        actor=admin,
        session_id=session_id,
        message_limit=message_limit,
    )


@router.post(
    "/sessions/{session_id}/messages",
    response_model=AdminChatMessageSubmitResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
async def submit_admin_chat_message(
    session_id: UUID,
    payload: AdminChatMessageSubmitRequest,
    http_request: Request,
    admin: AdminUserDep,
    service: AdminChatServiceDep,
    rate_limiter: RateLimitServiceDep,
) -> AdminChatMessageSubmitResponse:
    """Submit an admin analytics question and enqueue assistant generation."""
    await rate_limiter.enforce(
        RateLimitPolicy.ADMIN_CHAT,
        request=http_request,
        user=admin,
    )
    return await service.submit_message(
        actor=admin,
        session_id=session_id,
        request=payload,
    )


@router.get(
    "/sessions/{session_id}/messages/{message_id}/stream",
    response_class=StreamingResponse,
)
async def stream_admin_chat_message(
    session_id: UUID,
    message_id: UUID,
    admin: AdminUserDep,
    service: AdminChatServiceDep,
    stream_service: AgentStreamServiceDep,
    task_id: Annotated[str, Query(min_length=1)],
    after_id: Annotated[str, Query(pattern=r"^\d+-\d+$")] = "0-0",
    last_event_id: Annotated[str | None, Header(alias="Last-Event-ID")] = None,
) -> StreamingResponse:
    """Stream admin chat assistant generation events for a validated task."""
    await service.validate_message_stream(
        actor=admin,
        session_id=session_id,
        message_id=message_id,
        task_id=task_id,
    )
    cursor = _stream_cursor(after_id=after_id, last_event_id=last_event_id)
    return StreamingResponse(
        _iter_sse_events(
            stream_service=stream_service,
            task_id=task_id,
            after_id=cursor,
        ),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )


async def _iter_sse_events(
    *,
    stream_service: AgentStreamService,
    task_id: str,
    after_id: str,
):
    async for record in stream_service.iter_task_events(task_id, after_id=after_id):
        yield format_sse_record(record)


def _stream_cursor(*, after_id: str, last_event_id: str | None) -> str:
    if last_event_id is None or last_event_id == "":
        return after_id
    if not _is_stream_id(last_event_id):
        raise ValidationError("Invalid Last-Event-ID cursor")
    return last_event_id


def _is_stream_id(value: str) -> bool:
    parts = value.split("-", maxsplit=1)
    if len(parts) != 2:
        return False
    return all(part.isdigit() for part in parts)
