"""Worker-facing executor for the Playbook athlete chat graph."""

from __future__ import annotations

from collections.abc import Callable, Sequence
from typing import Any
from uuid import UUID

import structlog
from langchain_core.language_models import BaseChatModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.executors.conversation_title_executor import ConversationTitleExecutor
from app.agents.graph_provider import AgentGraphProvider
from app.agents.runtime_context import AthleteChatRuntimeContext
from app.agents.tools.knowledgebase import knowledgebase_organization_context
from app.core.config import Settings
from app.core.error_codes import ErrorCode
from app.core.exceptions import AppError
from app.infrastructure.knowledgebase import BaseKnowledgebaseProvider
from app.observability.agent_trace import build_graph_invoke_config
from app.repositories.conversations import ConversationMessageRepository
from app.services.agent_stream_service import AgentStreamService

logger = structlog.get_logger(__name__)

ATHLETE_CHAT_MODE = "athlete_chat"
ATHLETE_CHAT_PHASE = "respond"

TitleExecutorFactory = Callable[..., ConversationTitleExecutor]


class AthleteChatExecutor:
    """Execute the athlete chat graph for one persisted assistant placeholder."""

    def __init__(
        self,
        *,
        session: AsyncSession,
        chat_model: BaseChatModel,
        knowledgebase_provider: BaseKnowledgebaseProvider,
        stream_service: AgentStreamService,
        settings: Settings,
        title_model: BaseChatModel | None = None,
        checkpointer: Any | None = None,
        graph_provider: AgentGraphProvider | None = None,
        title_executor_factory: TitleExecutorFactory = ConversationTitleExecutor,
    ) -> None:
        self.session = session
        self.chat_model = chat_model
        self.title_model = title_model or chat_model
        self.knowledgebase_provider = knowledgebase_provider
        self.stream_service = stream_service
        self.settings = settings
        self.checkpointer = checkpointer
        self.graph_provider = graph_provider or AgentGraphProvider(
            chat_model=self.chat_model,
            title_model=self.title_model,
            settings=settings,
            checkpointer=checkpointer,
        )
        self.title_executor_factory = title_executor_factory
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
        attached_file_ids: Sequence[UUID],
    ) -> dict[str, Any]:
        """Run the athlete chat graph and return its persisted completion summary."""
        await self.stream_service.publish_progress(
            task_id,
            status="starting_agent",
            metadata={"conversation_id": str(conversation_id)},
        )
        graph = self.graph_provider.athlete_chat_graph()
        runtime_context = AthleteChatRuntimeContext(
            session=self.session,
            settings=self.settings,
            knowledgebase_provider=self.knowledgebase_provider,
            stream_service=self.stream_service,
        )
        config = build_graph_invoke_config(
            thread_id=conversation_id,
            phase=ATHLETE_CHAT_PHASE,
            mode=ATHLETE_CHAT_MODE,
            settings=self.settings,
            extra_configurable={
                "task_id": task_id,
                "assistant_message_id": str(assistant_message_id),
                "organization_id": str(organization_id),
                "attached_file_ids": [str(file_id) for file_id in attached_file_ids],
            },
        )
        initial_state = {
            "task_id": task_id,
            "conversation_id": str(conversation_id),
            "athlete_user_id": str(athlete_user_id),
            "user_message_id": str(user_message_id),
            "assistant_message_id": str(assistant_message_id),
            "organization_id": str(organization_id),
            "attached_file_ids": [str(file_id) for file_id in attached_file_ids],
        }

        completion_result: dict[str, Any] | None = None
        with knowledgebase_organization_context(str(organization_id)):
            async for part in graph.astream(
                initial_state,
                config=config,
                context=runtime_context,
                stream_mode=["updates", "custom"],
                version="v2",
            ):
                normalized = _normalize_stream_part(part)
                current_completion = _completion_from_part(normalized)
                if current_completion is not None:
                    completion_result = current_completion
                    continue
                if normalized["type"] in {"updates", "custom"}:
                    await self.stream_service.publish_langgraph_part(task_id, normalized)

        if completion_result is None:
            raise AppError(
                "Athlete chat graph finished without a completion result",
                ErrorCode.AGENT_FAILED,
                retryable=True,
            )

        conversation_title = await self._generate_conversation_title(
            task_id=task_id,
            conversation_id=conversation_id,
            athlete_user_id=athlete_user_id,
            user_message_id=user_message_id,
            assistant_message_id=assistant_message_id,
            organization_id=organization_id,
        )
        complete_payload = _completion_stream_payload(completion_result)
        if conversation_title:
            complete_payload["conversation_title"] = conversation_title
        await self.stream_service.publish_complete(task_id, data=complete_payload)
        return complete_payload

    async def _generate_conversation_title(
        self,
        *,
        task_id: str,
        conversation_id: UUID,
        athlete_user_id: UUID,
        user_message_id: UUID,
        assistant_message_id: UUID,
        organization_id: UUID,
    ) -> str | None:
        try:
            executor = self.title_executor_factory(
                session=self.session,
                title_model=self.title_model,
                settings=self.settings,
                checkpointer=self.checkpointer,
                graph_provider=self.graph_provider,
            )
            return await executor.execute(
                task_id=task_id,
                conversation_id=conversation_id,
                athlete_user_id=athlete_user_id,
                user_message_id=user_message_id,
                assistant_message_id=assistant_message_id,
                organization_id=organization_id,
            )
        except Exception as exc:  # noqa: BLE001
            logger.warning(
                "conversation_title_generation_failed",
                task_id=task_id,
                conversation_id=str(conversation_id),
                assistant_message_id=str(assistant_message_id),
                error_type=type(exc).__name__,
                exc_info=True,
            )
            return None

    async def mark_failed(
        self,
        *,
        task_id: str,
        assistant_message_id: UUID,
        error_type: str,
    ) -> None:
        """Mark an assistant placeholder as failed after task-level errors."""
        message = await self.message_repo.get(assistant_message_id)
        if message is None:
            logger.warning(
                "athlete_chat_failed_message_missing",
                task_id=task_id,
                assistant_message_id=str(assistant_message_id),
            )
            return
        await self.message_repo.update_status_and_content(
            message,
            status="failed",
            metadata={
                **message.message_metadata,
                "task_id": task_id,
                "agent_error_type": error_type,
            },
        )
        await self.session.commit()


def _normalize_stream_part(part: Any) -> dict[str, Any]:
    if isinstance(part, dict) and "type" in part:
        return part
    if isinstance(part, tuple) and len(part) == 2:
        stream_type, data = part
        return {"type": str(stream_type), "data": data}
    return {"type": "updates", "data": part}


def _completion_from_part(part: dict[str, Any]) -> dict[str, Any] | None:
    data = part.get("data")
    if not isinstance(data, dict):
        return None
    if isinstance(data.get("completion_result"), dict):
        return data["completion_result"]
    for node_update in data.values():
        if (
            isinstance(node_update, dict)
            and isinstance(node_update.get("completion_result"), dict)
        ):
            return node_update["completion_result"]
    return None


def _completion_stream_payload(completion_result: dict[str, Any]) -> dict[str, Any]:
    """Return public terminal stream data without duplicating the answer text."""
    return {
        key: value
        for key, value in completion_result.items()
        if key != "answer"
    }
