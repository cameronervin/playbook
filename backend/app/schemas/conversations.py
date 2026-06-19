"""Athlete conversation schemas."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.schemas.uploads import DirectUploadContract

ConversationFileExtractionStatus = Literal[
    "upload_pending",
    "uploaded",
    "extracting",
    "ready",
    "failed",
]


class ConversationCreateRequest(BaseModel):
    """Start a conversation from the athlete's first message."""

    content: str = Field(min_length=1)

    @field_validator("content")
    @classmethod
    def trim_content(cls, value: str) -> str:
        """Normalize accidental edge whitespace and reject empty content."""
        trimmed = value.strip()
        if not trimmed:
            raise ValueError("content must contain message content")
        return trimmed


class MessageSubmitRequest(BaseModel):
    """Submit a follow-up message to an existing athlete conversation."""

    content: str = Field(min_length=1)
    file_ids: list[UUID] = Field(default_factory=list)

    @field_validator("content")
    @classmethod
    def trim_content(cls, value: str) -> str:
        """Normalize accidental edge whitespace and reject empty content."""
        trimmed = value.strip()
        if not trimmed:
            raise ValueError("content must contain message content")
        return trimmed


class MessageSubmitResponse(BaseModel):
    """Stream metadata returned after enqueuing assistant generation."""

    user_message_id: UUID
    assistant_message_id: UUID
    task_id: str
    stream_url: str
    status: str


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
    extraction_status: ConversationFileExtractionStatus
    chunk_count: int
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class ConversationFileUploadRequest(BaseModel):
    """Create a direct-upload request for a conversation-scoped file."""

    filename: str = Field(min_length=1, max_length=500)
    content_type: str = Field(min_length=1, max_length=120)
    size_bytes: int = Field(gt=0)
    message_id: UUID | None = None

    @field_validator("filename")
    @classmethod
    def trim_filename(cls, value: str) -> str:
        """Normalize path-bearing browser filenames to the leaf filename."""
        trimmed = value.replace("\\", "/").rsplit("/", 1)[-1].strip()
        if not trimmed:
            raise ValueError("filename must not be empty")
        return trimmed

    @field_validator("content_type")
    @classmethod
    def trim_content_type(cls, value: str) -> str:
        """Normalize accidental whitespace around content type values."""
        trimmed = value.strip()
        if not trimmed:
            raise ValueError("content_type must not be empty")
        return trimmed


class ConversationFileUploadRequestResponse(BaseModel):
    """Conversation file summary plus direct browser upload contract."""

    file: ConversationFileSummaryResponse
    upload: DirectUploadContract


class ConversationDetailResponse(ConversationSummaryResponse):
    """Conversation detail response."""

    messages: list[ConversationMessageResponse] = Field(default_factory=list)
    files: list[ConversationFileSummaryResponse] = Field(default_factory=list)


class ConversationStartResponse(MessageSubmitResponse):
    """New conversation detail plus stream metadata for the first user turn."""

    conversation: ConversationDetailResponse
