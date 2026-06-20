"""Worker-facing executor for the Playbook conversation title graph."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any
from uuid import UUID

import structlog
from langchain_core.language_models import BaseChatModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.builders.graphs_builder import compile_conversation_title_graph
from app.core.config import Settings
from app.repositories.conversations import (
    ConversationMessageRepository,
    ConversationRepository,
)

logger = structlog.get_logger(__name__)

GraphFactory = Callable[..., Any]


class ConversationTitleExecutor:
    """Execute the title graph for a first-turn assistant response."""

    def __init__(
        self,
        *,
        session: AsyncSession,
        title_model: BaseChatModel,
        settings: Settings,
        checkpointer: Any | None = None,
        graph_factory: GraphFactory = compile_conversation_title_graph,
    ) -> None:
        self.session = session
        self.title_model = title_model
        self.settings = settings
        self.checkpointer = checkpointer
        self.graph_factory = graph_factory
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

        graph = self.graph_factory(
            title_model=self.title_model,
            session=self.session,
            checkpointer=self.checkpointer,
            app_settings=self.settings,
        )
        result = await graph.ainvoke(
            {
                "task_id": task_id,
                "conversation_id": str(conversation_id),
                "athlete_user_id": str(athlete_user_id),
                "organization_id": str(organization_id),
                "user_message_id": str(user_message_id),
                "assistant_message_id": str(assistant_message_id),
                "provisional_title": provisional_title,
            }
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
