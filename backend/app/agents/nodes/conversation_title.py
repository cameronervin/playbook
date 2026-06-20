"""Node factories for the Playbook conversation title graph."""

from __future__ import annotations

from typing import Any
from uuid import UUID

import structlog
from langchain_core.messages import HumanMessage
from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.states.conversation_title_state import (
    ConversationTitleState,
    ConversationTitleStructuredResponse,
)
from app.core.config import Settings
from app.core.exceptions import NotFoundError
from app.repositories.conversations import (
    ConversationMessageRepository,
    ConversationRepository,
)
from app.services.conversations.titles import normalize_ai_conversation_title

logger = structlog.get_logger(__name__)


def create_conversation_title_nodes(
    *,
    chains: dict[str, Any],
    session: AsyncSession,
    settings: Settings,
) -> dict[str, Any]:
    """Create all nodes needed by the conversation title graph."""
    conversation_repo = ConversationRepository(session)
    message_repo = ConversationMessageRepository(session)

    async def load_title_context(state: ConversationTitleState) -> dict[str, Any]:
        """Validate ownership and load the first-turn title context."""
        conversation_id = UUID(state["conversation_id"])
        athlete_user_id = UUID(state["athlete_user_id"])
        organization_id = UUID(state["organization_id"])
        user_message_id = UUID(state["user_message_id"])
        assistant_message_id = UUID(state["assistant_message_id"])

        conversation = await conversation_repo.get_for_athlete(
            conversation_id=conversation_id,
            organization_id=organization_id,
            athlete_id=athlete_user_id,
        )
        if conversation is None:
            raise NotFoundError("Conversation", str(conversation_id))

        user_message = await message_repo.get(user_message_id)
        assistant_message = await message_repo.get(assistant_message_id)
        if (
            user_message is None
            or user_message.conversation_id != conversation.id
            or user_message.role != "user"
        ):
            raise NotFoundError("User message", str(user_message_id))
        if (
            assistant_message is None
            or assistant_message.conversation_id != conversation.id
            or assistant_message.role != "assistant"
            or assistant_message.status != "complete"
        ):
            raise NotFoundError("Assistant message", str(assistant_message_id))

        provisional_title = str(state.get("provisional_title") or "").strip()
        return {
            "user_message_content": user_message.content,
            "assistant_answer": assistant_message.content,
            "topic_labels": [str(label) for label in assistant_message.topic_labels],
            "provisional_title": provisional_title,
        }

    async def generate_title(state: ConversationTitleState) -> dict[str, Any]:
        """Invoke the structured conversation title chain."""
        result = await chains["conversation_title"].ainvoke(
            {
                "messages": [
                    HumanMessage(content=_title_user_prompt(state)),
                ],
                "task_id": state.get("task_id", ""),
                "conversation_id": state["conversation_id"],
            }
        )
        structured = _structured_title_response(result)
        return {"generated_title": structured.title}

    async def save_title(state: ConversationTitleState) -> dict[str, Any]:
        """Persist the title if the provisional title is still current."""
        conversation_id = UUID(state["conversation_id"])
        athlete_user_id = UUID(state["athlete_user_id"])
        organization_id = UUID(state["organization_id"])
        provisional_title = state.get("provisional_title", "")
        title = normalize_ai_conversation_title(
            state.get("generated_title", ""),
            fallback=provisional_title,
        )
        conversation = await conversation_repo.get_for_athlete(
            conversation_id=conversation_id,
            organization_id=organization_id,
            athlete_id=athlete_user_id,
        )
        if conversation is None:
            raise NotFoundError("Conversation", str(conversation_id))
        if conversation.title not in {None, provisional_title}:
            logger.info(
                "conversation_title_update_skipped",
                conversation_id=str(conversation_id),
                reason="title_changed",
            )
            return {"conversation_title": None}

        await conversation_repo.update_title_if_current(
            conversation,
            title=title,
            expected_title=provisional_title,
        )
        await session.commit()
        logger.info(
            "conversation_title_updated",
            conversation_id=str(conversation_id),
            model=settings.LLM_TITLE_MODEL or "default",
        )
        return {"conversation_title": title}

    return {
        "load_title_context": load_title_context,
        "generate_title": generate_title,
        "save_title": save_title,
    }


def _title_user_prompt(state: ConversationTitleState) -> str:
    topic_labels = ", ".join(state.get("topic_labels", [])[:5]) or "none"
    return (
        "Create a title for this athlete support chat.\n\n"
        f"First user message:\n{state.get('user_message_content', '')}\n\n"
        f"Assistant answer:\n{state.get('assistant_answer', '')}\n\n"
        f"Topic labels: {topic_labels}\n"
        f"Fallback title: {state.get('provisional_title', '')}"
    )


def _structured_title_response(result: Any) -> ConversationTitleStructuredResponse:
    if isinstance(result, ConversationTitleStructuredResponse):
        return result
    if isinstance(result, dict):
        structured = result.get("structured_response", result)
        return ConversationTitleStructuredResponse.model_validate(structured)
    return ConversationTitleStructuredResponse.model_validate(result)
