"""Athlete conversation schemas."""

from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator


class ConversationCreateRequest(BaseModel):
    """Create a conversation from the athlete's first message."""

    initial_message: str = Field(min_length=1)

    @field_validator("initial_message")
    @classmethod
    def trim_initial_message(cls, value: str) -> str:
        """Normalize accidental edge whitespace and reject empty content."""
        trimmed = value.strip()
        if not trimmed:
            raise ValueError("initial_message must contain message content")
        return trimmed


class ConversationSummaryResponse(BaseModel):
    """Conversation list item."""

    id: UUID
    organization_id: UUID
    athlete_id: UUID
    title: str | None
    status: str
    last_message_at: datetime | None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class MessageCitationResponse(BaseModel):
    """Assistant message citation."""

    id: UUID
    message_id: UUID
    document_id: UUID | None
    chunk_id: UUID | None
    source_title: str
    source_metadata: dict[str, Any]
    rank: int
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class ConversationMessageResponse(BaseModel):
    """Conversation message with citations."""

    id: UUID
    conversation_id: UUID
    role: str
    content: str
    status: str
    safety_outcome: str | None
    topic_labels: list[Any]
    risk_labels: list[Any]
    metadata: dict[str, Any]
    citations: list[MessageCitationResponse] = Field(default_factory=list)
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class ConversationFileSummaryResponse(BaseModel):
    """Safe public summary of a conversation-scoped file attachment."""

    id: UUID
    conversation_id: UUID
    message_id: UUID | None
    filename: str
    content_type: str
    size_bytes: int
    extraction_status: str
    chunk_count: int
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class ConversationDetailResponse(ConversationSummaryResponse):
    """Conversation detail response."""

    messages: list[ConversationMessageResponse] = Field(default_factory=list)
    files: list[ConversationFileSummaryResponse] = Field(default_factory=list)
