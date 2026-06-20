"""Graph state schemas for agent workflows."""

from app.agents.states.athlete_chat_state import (
    AthleteChatAnswerType,
    AthleteChatState,
    AthleteChatStructuredResponse,
)
from app.agents.states.conversation_title_state import (
    ConversationTitleState,
    ConversationTitleStructuredResponse,
)

__all__ = [
    "AthleteChatAnswerType",
    "AthleteChatState",
    "AthleteChatStructuredResponse",
    "ConversationTitleState",
    "ConversationTitleStructuredResponse",
]
