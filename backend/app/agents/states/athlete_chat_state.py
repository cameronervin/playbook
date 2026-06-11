"""State and structured output schemas for the Playbook athlete chat graph."""

from __future__ import annotations

from typing import Annotated, Literal, TypedDict

from langchain_core.messages import BaseMessage
from langgraph.graph.message import add_messages
from pydantic import BaseModel, Field

AthleteChatAnswerType = Literal[
    "grounded_answer",
    "refusal",
    "emergency_instruction",
    "unsupported",
]


class AthleteChatStructuredResponse(BaseModel):
    """Validated final response produced by the athlete chat agent."""

    answer: str = Field(..., description="Final athlete-facing answer text.")
    answer_type: AthleteChatAnswerType = Field(
        default="grounded_answer",
        description="Classification for persistence and analytics.",
    )
    cited_source_keys: list[str] = Field(
        default_factory=list,
        description="Source keys from retrieved KB context that support the answer.",
    )
    topic_labels: list[str] = Field(
        default_factory=list,
        description="Analytics topic labels such as nil, compliance, or process.",
    )
    risk_labels: list[str] = Field(
        default_factory=list,
        description="Analytics risk labels such as compliance or recruiting.",
    )
    safety_outcome: str | None = Field(
        default=None,
        description="Optional safety outcome when the answer is a refusal.",
    )


class AthleteChatState(TypedDict, total=False):
    """LangGraph state for one athlete chat task.

    Non-message fields are intentionally JSON-safe so Postgres checkpoints do not
    need to serialize repository objects, provider objects, or source dataclasses.
    """

    messages: Annotated[list[BaseMessage], add_messages]
    task_id: str
    conversation_id: str
    athlete_user_id: str
    user_message_id: str
    assistant_message_id: str
    organization_id: str
    attached_file_ids: list[str]

    user_message_content: str
    should_bypass_agent: bool
    requires_kb_support: bool

    answer: str
    answer_type: AthleteChatAnswerType
    cited_source_keys: list[str]
    topic_labels: list[str]
    risk_labels: list[str]
    safety_outcome: str | None

    completion_result: dict[str, object]
