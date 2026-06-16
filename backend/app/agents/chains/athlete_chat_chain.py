"""Athlete chat create_agent chain."""

from __future__ import annotations

from typing import Any, Sequence

from langchain.agents import create_agent
from langchain.agents.structured_output import ToolStrategy
from langchain_core.language_models import BaseChatModel
from langchain_core.tools import BaseTool

from app.agents.context.middleware.athlete_chat_middleware import (
    create_athlete_chat_middleware,
)
from app.agents.prompts.athlete_chat_prompt import ATHLETE_CHAT_SYSTEM_PROMPT
from app.agents.states.athlete_chat_state import (
    AthleteChatState,
    AthleteChatStructuredResponse,
)
from app.core.config import Settings


def create_athlete_chat_chain(
    *,
    chat_model: BaseChatModel,
    tools: Sequence[BaseTool],
    checkpointer: Any | None = None,
    system_prompt: str = ATHLETE_CHAT_SYSTEM_PROMPT,
    settings: Settings | None = None,
) -> Any:
    """Create the Playbook athlete chat agent graph."""
    return create_agent(
        model=chat_model,
        tools=list(tools),
        system_prompt=system_prompt,
        middleware=[create_athlete_chat_middleware(settings=settings)],
        state_schema=AthleteChatState,
        response_format=ToolStrategy(AthleteChatStructuredResponse),
        checkpointer=checkpointer,
    )
