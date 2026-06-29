"""State and structured output schemas for admin analytics chat."""

from __future__ import annotations

from typing import Any, Literal

from langchain.agents import AgentState
from pydantic import BaseModel, Field

AdminChatAnswerType = Literal["analytics_answer", "refusal", "unsupported"]
AdminChatReferenceType = Literal["metric", "dashboard_insight", "query"]


class AdminChatReference(BaseModel):
    """Reference requested by the admin chat agent."""

    type: AdminChatReferenceType
    id: str = Field(..., description="Reference ID within the allowed context.")


class AdminChatStructuredResponse(BaseModel):
    """Validated admin chat output produced by the agent."""

    answer: str = Field(..., description="Admin-facing response text.")
    answer_type: AdminChatAnswerType = Field(
        ...,
        description="analytics_answer, refusal, or unsupported.",
    )
    references: list[AdminChatReference] = Field(
        default_factory=list,
        description="Metric, dashboard insight, or anonymized query references.",
    )


class AdminChatState(AgentState[AdminChatStructuredResponse], total=False):
    """LangGraph state for one admin analytics chat turn.

    Keep fields JSON-safe so checkpoint payloads do not serialize sessions,
    repositories, ORM objects, or analytics DTO instances.
    """

    task_id: str
    session_id: str
    admin_user_id: str
    user_message_id: str
    assistant_message_id: str
    organization_id: str
    window_start: str
    window_end: str

    question: str
    snapshot_context: str
    dashboard_insight_context: str
    allowed_references: list[dict[str, str]]

    should_bypass_agent: bool
    answer: str
    answer_type: AdminChatAnswerType
    references: list[dict[str, str]]

    completion_result: dict[str, Any]
