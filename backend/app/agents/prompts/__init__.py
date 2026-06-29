"""System prompt strings for agent chains."""

from app.agents.prompts.admin_chat_prompt import ADMIN_CHAT_SYSTEM_PROMPT
from app.agents.prompts.athlete_chat_prompt import ATHLETE_CHAT_SYSTEM_PROMPT
from app.agents.prompts.dashboard_insights_prompt import (
    DASHBOARD_INSIGHTS_SYSTEM_PROMPT,
)

__all__ = [
    "ADMIN_CHAT_SYSTEM_PROMPT",
    "ATHLETE_CHAT_SYSTEM_PROMPT",
    "DASHBOARD_INSIGHTS_SYSTEM_PROMPT",
]
