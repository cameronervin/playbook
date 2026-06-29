"""Prompt composers: base prompt + active tool snippets -> final system prompt."""

from app.agents.context.prompt_composers.athlete_chat_prompt_composer import (
    build_athlete_chat_prompt,
    build_athlete_chat_prompts,
)
from app.agents.context.prompt_composers.dashboard_insights_prompt_composer import (
    build_dashboard_insights_prompt,
    build_dashboard_insights_prompts,
)

__all__ = [
    "build_athlete_chat_prompt",
    "build_athlete_chat_prompts",
    "build_dashboard_insights_prompt",
    "build_dashboard_insights_prompts",
]
