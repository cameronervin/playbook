"""Dashboard insights create_agent chain."""

from __future__ import annotations

from typing import Any, Sequence

from langchain.agents import create_agent
from langchain.agents.structured_output import ToolStrategy
from langchain_core.language_models import BaseChatModel
from langchain_core.tools import BaseTool

from app.agents.context.middleware.dashboard_insights_middleware import (
    create_dashboard_insights_middleware,
)
from app.agents.prompts.dashboard_insights_prompt import (
    DASHBOARD_INSIGHTS_SYSTEM_PROMPT,
)
from app.agents.runtime_context import DashboardInsightsRuntimeContext
from app.agents.states.dashboard_insights_state import (
    DashboardInsightsState,
    DashboardInsightsStructuredResponse,
)
from app.core.config import Settings


def create_dashboard_insights_chain(
    *,
    chat_model: BaseChatModel,
    tools: Sequence[BaseTool],
    checkpointer: Any | None = None,
    system_prompt: str = DASHBOARD_INSIGHTS_SYSTEM_PROMPT,
    settings: Settings | None = None,
) -> Any:
    """Create the Playbook dashboard insights structured agent."""
    return create_agent(
        model=chat_model,
        tools=list(tools),
        system_prompt=system_prompt,
        middleware=[create_dashboard_insights_middleware(settings=settings)],
        state_schema=DashboardInsightsState,
        context_schema=DashboardInsightsRuntimeContext,
        response_format=ToolStrategy(DashboardInsightsStructuredResponse),
        checkpointer=checkpointer,
    )
