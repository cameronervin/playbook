"""Chain construction for Playbook agent workflows."""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any

from langchain_core.language_models import BaseChatModel
from langchain_core.tools import BaseTool

from app.agents.chains.athlete_chat_chain import create_athlete_chat_chain
from app.agents.chains.conversation_title_chain import create_conversation_title_chain
from app.agents.context.prompt_composers.athlete_chat_prompt_composer import (
    build_athlete_chat_prompts,
)
from app.core.config import Settings


def create_athlete_chat_chain_set(
    *,
    chat_model: BaseChatModel,
    tools: Sequence[BaseTool],
    settings: Settings,
) -> dict[str, Any]:
    """Create the chains required by the athlete chat workflow."""
    prompts = build_athlete_chat_prompts([tool.name for tool in tools])
    return {
        "athlete_chat": create_athlete_chat_chain(
            chat_model=chat_model,
            tools=tools,
            system_prompt=prompts["athlete_chat"],
            settings=settings,
        ),
    }


def create_conversation_title_chain_set(
    *,
    title_model: BaseChatModel,
    settings: Settings,
) -> dict[str, Any]:
    """Create the chains required by the conversation title workflow."""
    return {
        "conversation_title": create_conversation_title_chain(
            title_model=title_model,
        )
    }
