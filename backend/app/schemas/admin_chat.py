"""Admin analytics chat schemas."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator

AdminChatAnswerType = Literal["analytics_answer", "refusal", "unsupported"]
AdminChatMessageRole = Literal["user", "assistant"]
AdminChatMessageStatus = Literal["complete", "streaming", "failed"]
AdminChatReferenceType = Literal["metric", "dashboard_insight", "query"]
AdminChatSessionStatus = Literal["active", "archived"]


class AdminChatReference(BaseModel):
    """Reference returned with an admin chat answer."""

    type: AdminChatReferenceType
    id: str


class AdminChatSessionCreateRequest(BaseModel):
    """Create an admin analytics chat session."""

    title: str | None = Field(default=None, max_length=255)
    context_window_start: datetime | None = None
    context_window_end: datetime | None = None

    @model_validator(mode="after")
    def validate_window_pair(self) -> "AdminChatSessionCreateRequest":
        """Require explicit session window bounds to be provided together."""
        if (self.context_window_start is None) != (self.context_window_end is None):
            raise ValueError(
                "context_window_start and context_window_end must be provided together"
            )
        return self


class AdminChatMessageSubmitRequest(BaseModel):
    """Submit an admin analytics question."""

    question: str = Field(min_length=1, max_length=4000)
    window: str | None = Field(default=None, pattern=r"^[1-9][0-9]*d$")
    window_start: datetime | None = None
    window_end: datetime | None = None

    @model_validator(mode="after")
    def validate_window_selection(self) -> "AdminChatMessageSubmitRequest":
        """Reject conflicting shorthand and explicit windows."""
        if self.window and (self.window_start is not None or self.window_end is not None):
            raise ValueError("window cannot be combined with window_start/window_end")
        if (self.window_start is None) != (self.window_end is None):
            raise ValueError("window_start and window_end must be provided together")
        self.question = self.question.strip()
        if not self.question:
            raise ValueError("question cannot be blank")
        return self


class AdminChatSessionResponse(BaseModel):
    """Admin analytics chat session summary."""

    id: UUID
    title: str | None = None
    status: AdminChatSessionStatus
    context_window_start: datetime | None = None
    context_window_end: datetime | None = None
    last_message_at: datetime | None = None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class AdminChatMessageResponse(BaseModel):
    """Admin analytics chat message."""

    id: UUID
    session_id: UUID
    role: AdminChatMessageRole
    content: str
    status: AdminChatMessageStatus
    references: list[AdminChatReference] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)
    answer_type: AdminChatAnswerType | None = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class AdminChatSessionDetailResponse(AdminChatSessionResponse):
    """Admin analytics chat session with messages."""

    messages: list[AdminChatMessageResponse] = Field(default_factory=list)


class AdminChatMessageSubmitResponse(BaseModel):
    """Response returned after enqueueing admin chat generation."""

    session_id: UUID
    user_message_id: UUID
    assistant_message_id: UUID
    task_id: str
    stream_url: str
    status: AdminChatMessageStatus
