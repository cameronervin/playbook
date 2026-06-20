"""State and structured output schemas for conversation title generation."""

from __future__ import annotations

from typing import Annotated, TypedDict

from langchain_core.messages import BaseMessage
from langgraph.graph.message import add_messages
from pydantic import BaseModel, Field


class ConversationTitleStructuredResponse(BaseModel):
    """Validated title output produced by the conversation title agent."""

    title: str = Field(
        ...,
        description="A concise 3-7 word conversation title.",
    )


class ConversationTitleState(TypedDict, total=False):
    """LangGraph state for one conversation title generation run."""

    messages: Annotated[list[BaseMessage], add_messages]
    task_id: str
    conversation_id: str
    athlete_user_id: str
    organization_id: str
    user_message_id: str
    assistant_message_id: str
    provisional_title: str

    user_message_content: str
    assistant_answer: str
    topic_labels: list[str]
    generated_title: str
    conversation_title: str
