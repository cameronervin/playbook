"""Graph state schemas for agent workflows."""

from app.agents.states.admin_chat_state import (
    AdminChatAnswerType,
    AdminChatReference,
    AdminChatState,
    AdminChatStructuredResponse,
)
from app.agents.states.athlete_chat_state import (
    AthleteChatAnswerType,
    AthleteChatState,
    AthleteChatStructuredResponse,
)
from app.agents.states.conversation_title_state import (
    ConversationTitleState,
    ConversationTitleStructuredResponse,
)
from app.agents.states.dashboard_insights_state import (
    DashboardInsightsState,
    DashboardInsightsStructuredResponse,
)

__all__ = [
    "AthleteChatAnswerType",
    "AthleteChatState",
    "AthleteChatStructuredResponse",
    "AdminChatAnswerType",
    "AdminChatReference",
    "AdminChatState",
    "AdminChatStructuredResponse",
    "ConversationTitleState",
    "ConversationTitleStructuredResponse",
    "DashboardInsightsState",
    "DashboardInsightsStructuredResponse",
]
