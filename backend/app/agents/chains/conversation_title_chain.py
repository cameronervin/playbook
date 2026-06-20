"""Conversation title create_agent chain."""

from __future__ import annotations

from typing import Any

from langchain.agents import create_agent
from langchain.agents.structured_output import ToolStrategy
from langchain_core.language_models import BaseChatModel

from app.agents.prompts.conversation_title_prompt import (
    CONVERSATION_TITLE_SYSTEM_PROMPT,
)
from app.agents.states.conversation_title_state import (
    ConversationTitleState,
    ConversationTitleStructuredResponse,
)


def create_conversation_title_chain(
    *,
    title_model: BaseChatModel,
    checkpointer: Any | None = None,
    system_prompt: str = CONVERSATION_TITLE_SYSTEM_PROMPT,
) -> Any:
    """Create the Playbook conversation title agent graph."""
    return create_agent(
        model=title_model,
        tools=[],
        system_prompt=system_prompt,
        state_schema=ConversationTitleState,
        response_format=ToolStrategy(ConversationTitleStructuredResponse),
        checkpointer=checkpointer,
    )
