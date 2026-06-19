"""Athlete conversation routes."""

from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Header, Query, status
from fastapi.responses import StreamingResponse

from app.api.v1.dependencies import (
    AgentStreamServiceDep,
    AthleteUserDep,
    ConversationFileUploadServiceDep,
    ConversationServiceDep,
)
from app.core.exceptions import ValidationError
from app.schemas.conversations import (
    ConversationCreateRequest,
    ConversationDetailResponse,
    ConversationFileSummaryResponse,
    ConversationFileUploadRequest,
    ConversationFileUploadRequestResponse,
    ConversationStartResponse,
    ConversationSummaryResponse,
    MessageSubmitRequest,
    MessageSubmitResponse,
)
from app.schemas.uploads import UploadCompleteRequest
from app.services.agent_stream_service import AgentStreamService, format_sse_record

router = APIRouter(prefix="/conversations", tags=["Conversations"])


@router.get("", response_model=list[ConversationSummaryResponse])
async def list_conversations(
    athlete: AthleteUserDep,
    service: ConversationServiceDep,
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> list[ConversationSummaryResponse]:
    """List current athlete conversations."""
    return await service.list_for_athlete(
        athlete=athlete,
        limit=limit,
        offset=offset,
    )


@router.post(
    "",
    response_model=ConversationStartResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
async def create_conversation(
    request: ConversationCreateRequest,
    athlete: AthleteUserDep,
    service: ConversationServiceDep,
) -> ConversationStartResponse:
    """Start a current-athlete conversation and enqueue assistant generation."""
    return await service.create(athlete=athlete, request=request)


@router.get("/{conversation_id}", response_model=ConversationDetailResponse)
async def get_conversation(
    conversation_id: UUID,
    athlete: AthleteUserDep,
    service: ConversationServiceDep,
    message_limit: Annotated[int, Query(ge=1, le=500)] = 100,
) -> ConversationDetailResponse:
    """Get current athlete conversation details."""
    return await service.get_detail(
        athlete=athlete,
        conversation_id=conversation_id,
        message_limit=message_limit,
    )


@router.post(
    "/{conversation_id}/files",
    response_model=ConversationFileUploadRequestResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_conversation_file_upload_request(
    conversation_id: UUID,
    request: ConversationFileUploadRequest,
    athlete: AthleteUserDep,
    service: ConversationFileUploadServiceDep,
) -> ConversationFileUploadRequestResponse:
    """Create a direct-upload request for a current-athlete conversation file."""
    return await service.create_file_upload_request(
        athlete=athlete,
        conversation_id=conversation_id,
        request=request,
    )


@router.post(
    "/{conversation_id}/files/{file_id}/upload-complete",
    response_model=ConversationFileSummaryResponse,
)
async def complete_conversation_file_upload(
    conversation_id: UUID,
    file_id: UUID,
    request: UploadCompleteRequest,
    athlete: AthleteUserDep,
    service: ConversationFileUploadServiceDep,
) -> ConversationFileSummaryResponse:
    """Verify a direct-uploaded conversation file and queue private ingest."""
    return await service.complete_file_upload(
        athlete=athlete,
        conversation_id=conversation_id,
        file_id=file_id,
        request=request,
    )


@router.post(
    "/{conversation_id}/messages",
    response_model=MessageSubmitResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
async def submit_message(
    conversation_id: UUID,
    request: MessageSubmitRequest,
    athlete: AthleteUserDep,
    service: ConversationServiceDep,
) -> MessageSubmitResponse:
    """Submit a follow-up message and enqueue assistant generation."""
    return await service.submit_message(
        athlete=athlete,
        conversation_id=conversation_id,
        request=request,
    )


@router.get(
    "/{conversation_id}/messages/{message_id}/stream",
    response_class=StreamingResponse,
)
async def stream_message(
    conversation_id: UUID,
    message_id: UUID,
    athlete: AthleteUserDep,
    service: ConversationServiceDep,
    stream_service: AgentStreamServiceDep,
    task_id: Annotated[str, Query(min_length=1)],
    after_id: Annotated[str, Query(pattern=r"^\d+-\d+$")] = "0-0",
    last_event_id: Annotated[str | None, Header(alias="Last-Event-ID")] = None,
) -> StreamingResponse:
    """Stream assistant generation events for a validated task."""
    await service.validate_message_stream(
        athlete=athlete,
        conversation_id=conversation_id,
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
