"""Athlete conversation routes."""

from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Query, status

from app.api.v1.dependencies import AthleteUserDep, ConversationServiceDep
from app.schemas.conversations import (
    ConversationCreateRequest,
    ConversationDetailResponse,
    ConversationSummaryResponse,
)

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
    response_model=ConversationDetailResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_conversation(
    request: ConversationCreateRequest,
    athlete: AthleteUserDep,
    service: ConversationServiceDep,
) -> ConversationDetailResponse:
    """Create a current-athlete conversation with an initial user message."""
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
