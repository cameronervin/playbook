"""Worker-facing executor for the Playbook conversation title graph."""

from __future__ import annotations

from typing import Any
from uuid import UUID

import structlog
from langchain_core.language_models import BaseChatModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.graph_provider import AgentGraphProvider
from app.agents.runtime_context import ConversationTitleRuntimeContext
from app.core.config import Settings
from app.observability.agent_trace import build_graph_invoke_config
from app.repositories.conversations import (
    ConversationMessageRepository,
    ConversationRepository,
)

logger = structlog.get_logger(__name__)

CONVERSATION_TITLE_MODE = "conversation_title"
CONVERSATION_TITLE_PHASE = "title"


class ConversationTitleExecutor:
    """Execute the title graph for a first-turn assistant response."""

    def __init__(
        self,
        *,
        session: AsyncSession,
        title_model: BaseChatModel,
        settings: Settings,
        checkpointer: Any | None = None,
        graph_provider: AgentGraphProvider | None = None,
    ) -> None:
        self.session = session
        self.title_model = title_model
        self.settings = settings
        self.checkpointer = checkpointer
        self.graph_provider = graph_provider or AgentGraphProvider(
            chat_model=title_model,
            title_model=title_model,
            settings=settings,
            checkpointer=checkpointer,
        )
        self.conversation_repo = ConversationRepository(session)
        self.message_repo = ConversationMessageRepository(session)

    async def execute(
        self,
        *,
        task_id: str,
        conversation_id: UUID,
        athlete_user_id: UUID,
        user_message_id: UUID,
        assistant_message_id: UUID,
        organization_id: UUID,
    ) -> str | None:
        """Run title generation when this assistant task is title-eligible."""
        provisional_title = await self._eligible_provisional_title(
            task_id=task_id,
            conversation_id=conversation_id,
            athlete_user_id=athlete_user_id,
            assistant_message_id=assistant_message_id,
            organization_id=organization_id,
        )
        if provisional_title is None:
            return None

        graph = self.graph_provider.conversation_title_graph()
        runtime_context = ConversationTitleRuntimeContext(
            session=self.session,
            settings=self.settings,
        )
        initial_state = {
            "task_id": task_id,
            "conversation_id": str(conversation_id),
            "athlete_user_id": str(athlete_user_id),
            "organization_id": str(organization_id),
            "user_message_id": str(user_message_id),
            "assistant_message_id": str(assistant_message_id),
            "provisional_title": provisional_title,
        }
        config = build_graph_invoke_config(
            thread_id=conversation_id,
            phase=CONVERSATION_TITLE_PHASE,
            mode=CONVERSATION_TITLE_MODE,
            settings=self.settings,
            extra_configurable={
                "checkpoint_ns": f"{CONVERSATION_TITLE_MODE}:{assistant_message_id}",
                "task_id": task_id,
                "assistant_message_id": str(assistant_message_id),
                "organization_id": str(organization_id),
                "user_message_id": str(user_message_id),
            },
        )
        result = await graph.ainvoke(
            initial_state,
            config=config,
            context=runtime_context,
        )
        title = result.get("conversation_title") if isinstance(result, dict) else None
        return title if isinstance(title, str) and title.strip() else None

    async def _eligible_provisional_title(
        self,
        *,
        task_id: str,
        conversation_id: UUID,
        athlete_user_id: UUID,
        assistant_message_id: UUID,
        organization_id: UUID,
    ) -> str | None:
        assistant_message = await self.message_repo.get(assistant_message_id)
        if assistant_message is None:
            return None
        metadata = assistant_message.message_metadata
        if (
            metadata.get("task_id") != task_id
            or metadata.get("is_first_turn") is not True
            or assistant_message.status != "complete"
        ):
            return None

        provisional_title = str(metadata.get("provisional_title") or "").strip()
        if not provisional_title:
            return None

        conversation = await self.conversation_repo.get_for_athlete(
            conversation_id=conversation_id,
            organization_id=organization_id,
            athlete_id=athlete_user_id,
        )
        if conversation is None:
            return None
        if conversation.title not in {None, provisional_title}:
            logger.info(
                "conversation_title_generation_skipped",
                conversation_id=str(conversation_id),
                reason="title_changed",
            )
            return None
        return provisional_title
