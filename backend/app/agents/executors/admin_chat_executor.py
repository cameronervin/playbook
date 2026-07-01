"""Worker-facing executor for the Playbook admin chat graph."""

from __future__ import annotations

from typing import Any
from uuid import UUID

import structlog
from langchain_core.language_models import BaseChatModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.graph_provider import AgentGraphProvider
from app.agents.runtime_context import AdminChatRuntimeContext
from app.core.config import Settings
from app.core.error_codes import ErrorCode
from app.core.exceptions import AppError
from app.observability.agent_trace import build_graph_invoke_config
from app.repositories.admin_chat import AdminChatMessageRepository
from app.services.agent_stream_service import AgentStreamService

logger = structlog.get_logger(__name__)

ADMIN_CHAT_MODE = "admin_chat"
ADMIN_CHAT_PHASE = "respond"


class AdminChatExecutor:
    """Execute the admin chat graph for one persisted assistant placeholder."""

    def __init__(
        self,
        *,
        session: AsyncSession,
        chat_model: BaseChatModel,
        stream_service: AgentStreamService,
        settings: Settings,
        checkpointer: Any | None = None,
        graph_provider: AgentGraphProvider | None = None,
    ) -> None:
        self.session = session
        self.chat_model = chat_model
        self.stream_service = stream_service
        self.settings = settings
        self.checkpointer = checkpointer
        self.graph_provider = graph_provider or AgentGraphProvider(
            chat_model=self.chat_model,
            title_model=self.chat_model,
            settings=settings,
            checkpointer=checkpointer,
        )
        self.message_repo = AdminChatMessageRepository(session)

    async def execute(
        self,
        *,
        task_id: str,
        session_id: UUID,
        admin_user_id: UUID,
        user_message_id: UUID,
        assistant_message_id: UUID,
        organization_id: UUID,
        window_start: str,
        window_end: str,
    ) -> dict[str, Any]:
        """Run the admin chat graph and return its persisted completion summary."""
        await self.stream_service.publish_progress(
            task_id,
            status="starting_agent",
            metadata={"session_id": str(session_id)},
        )
        graph = self.graph_provider.admin_chat_graph()
        runtime_context = AdminChatRuntimeContext(
            session=self.session,
            settings=self.settings,
            stream_service=self.stream_service,
        )
        config = build_graph_invoke_config(
            thread_id=session_id,
            phase=ADMIN_CHAT_PHASE,
            mode=ADMIN_CHAT_MODE,
            settings=self.settings,
            extra_configurable={
                "task_id": task_id,
                "session_id": str(session_id),
                "user_message_id": str(user_message_id),
                "assistant_message_id": str(assistant_message_id),
                "organization_id": str(organization_id),
            },
        )
        initial_state = {
            "task_id": task_id,
            "session_id": str(session_id),
            "admin_user_id": str(admin_user_id),
            "user_message_id": str(user_message_id),
            "assistant_message_id": str(assistant_message_id),
            "organization_id": str(organization_id),
            "window_start": window_start,
            "window_end": window_end,
        }

        completion_result: dict[str, Any] | None = None
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
                "Admin chat graph finished without a completion result",
                ErrorCode.AGENT_FAILED,
                retryable=True,
                details={"session_id": str(session_id)},
            )

        complete_payload = _completion_stream_payload(completion_result)
        await self.stream_service.publish_complete(task_id, data=complete_payload)
        return complete_payload

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
                "admin_chat_failed_message_missing",
                task_id=task_id,
                assistant_message_id=str(assistant_message_id),
            )
            return
        await self.message_repo.update_status_content_references(
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
    """Return public terminal stream data without duplicating answer text."""
    return {
        key: value
        for key, value in completion_result.items()
        if key != "answer"
    }
