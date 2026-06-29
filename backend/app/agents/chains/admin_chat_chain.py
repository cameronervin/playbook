"""Admin chat create_agent chain."""

from __future__ import annotations

from typing import Any, Sequence

from langchain.agents import create_agent
from langchain.agents.structured_output import ToolStrategy
from langchain_core.language_models import BaseChatModel
from langchain_core.tools import BaseTool

from app.agents.context.middleware.admin_chat_middleware import (
    create_admin_chat_middleware,
)
from app.agents.prompts.admin_chat_prompt import ADMIN_CHAT_SYSTEM_PROMPT
from app.agents.runtime_context import AdminChatRuntimeContext
from app.agents.states.admin_chat_state import (
    AdminChatState,
    AdminChatStructuredResponse,
)
from app.core.config import Settings


def create_admin_chat_chain(
    *,
    chat_model: BaseChatModel,
    tools: Sequence[BaseTool],
    checkpointer: Any | None = None,
    system_prompt: str = ADMIN_CHAT_SYSTEM_PROMPT,
    settings: Settings | None = None,
) -> Any:
    """Create the Playbook admin chat structured agent."""
    return create_agent(
        model=chat_model,
        tools=list(tools),
        system_prompt=system_prompt,
        middleware=[create_admin_chat_middleware(settings=settings)],
        state_schema=AdminChatState,
        context_schema=AdminChatRuntimeContext,
        response_format=ToolStrategy(AdminChatStructuredResponse),
        checkpointer=checkpointer,
    )
