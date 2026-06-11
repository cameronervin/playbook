"""Celery task registration for backend async workflows."""

from __future__ import annotations

from typing import Any
from uuid import UUID

import structlog

from app.agents.executors.athlete_chat_executor import AthleteChatExecutor
from app.core.config import get_settings
from app.infrastructure.checkpointer import (
    cleanup_checkpointer_pool,
    create_checkpointer,
    create_checkpointer_pool,
)
from app.infrastructure.knowledgebase import get_kb_provider
from app.infrastructure.llm import get_llm_provider
from app.infrastructure.streaming import get_agent_stream_provider
from app.services.agent_stream_service import AgentStreamService
from app.workers.app import backend_worker, run_async
from app.workers.queues import WorkerTaskName
from app.workers.session import worker_db_session

logger = structlog.get_logger(__name__)
TASK_MAX_RETRIES = backend_worker.conf.playbook_task_max_retries


def _raise_scaffold_not_implemented(task_name: WorkerTaskName, **context: Any) -> None:
    logger.info(
        "backend_worker_task_stub_invoked",
        task_name=task_name.value,
        **context,
    )
    raise NotImplementedError(f"{task_name.value} is scaffolded but not implemented")


@backend_worker.task(
    bind=True,
    name=WorkerTaskName.RUN_ATHLETE_CHAT.value,
    max_retries=TASK_MAX_RETRIES,
)
def run_athlete_chat_task(
    self: Any,
    *,
    conversation_id: str,
    athlete_user_id: str,
    user_message_id: str,
    assistant_message_id: str,
    organization_id: str,
    attached_file_ids: list[str] | None = None,
) -> dict[str, Any]:
    """Execute the Phase 2 athlete chat agent for one persisted user turn."""
    task_id = str(self.request.id)
    logger.info(
        "backend_worker_athlete_chat_invoked",
        task_id=task_id,
        conversation_id=conversation_id,
        user_message_id=user_message_id,
        assistant_message_id=assistant_message_id,
        organization_id=organization_id,
        attached_file_count=len(attached_file_ids or []),
    )
    return run_async(
        _run_athlete_chat_agent(
            task_id=task_id,
            conversation_id=conversation_id,
            athlete_user_id=athlete_user_id,
            user_message_id=user_message_id,
            assistant_message_id=assistant_message_id,
            organization_id=organization_id,
            attached_file_ids=attached_file_ids or [],
        )
    )


async def _run_athlete_chat_agent(
    *,
    task_id: str,
    conversation_id: str,
    athlete_user_id: str,
    user_message_id: str,
    assistant_message_id: str,
    organization_id: str,
    attached_file_ids: list[str],
) -> dict[str, Any]:
    stream_service = AgentStreamService(get_agent_stream_provider())
    checkpointer_pool = None
    try:
        settings = get_settings()
        checkpointer_pool = await create_checkpointer_pool(settings)
        checkpointer = await create_checkpointer(checkpointer_pool)
        async with worker_db_session(settings) as session:
            executor = AthleteChatExecutor(
                session=session,
                chat_model=get_llm_provider(app_settings=settings).get_chat_model(),
                knowledgebase_provider=get_kb_provider(app_settings=settings),
                stream_service=stream_service,
                settings=settings,
                checkpointer=checkpointer,
            )
            return await executor.execute(
                task_id=task_id,
                conversation_id=UUID(conversation_id),
                athlete_user_id=UUID(athlete_user_id),
                user_message_id=UUID(user_message_id),
                assistant_message_id=UUID(assistant_message_id),
                organization_id=UUID(organization_id),
                attached_file_ids=[UUID(file_id) for file_id in attached_file_ids],
            )
    except Exception as exc:  # noqa: BLE001
        logger.error(
            "athlete_chat_task_failed",
            task_id=task_id,
            conversation_id=conversation_id,
            assistant_message_id=assistant_message_id,
            error_type=type(exc).__name__,
            exc_info=True,
        )
        try:
            async with worker_db_session(get_settings()) as session:
                executor = AthleteChatExecutor(
                    session=session,
                    chat_model=object(),  # type: ignore[arg-type]
                    knowledgebase_provider=get_kb_provider(),
                    stream_service=stream_service,
                    settings=get_settings(),
                )
                await executor.mark_failed(
                    task_id=task_id,
                    assistant_message_id=UUID(assistant_message_id),
                    error_type=type(exc).__name__,
                )
        except Exception as mark_exc:  # noqa: BLE001
            logger.error(
                "athlete_chat_mark_failed_error",
                task_id=task_id,
                assistant_message_id=assistant_message_id,
                error_type=type(mark_exc).__name__,
                exc_info=True,
            )
        await stream_service.publish_error(
            task_id,
            message="Athlete chat generation failed.",
            code="agent_failed",
            metadata={
                "conversation_id": conversation_id,
                "assistant_message_id": assistant_message_id,
                "error_type": type(exc).__name__,
            },
        )
        return {
            "status": "failed",
            "code": "agent_failed",
            "task_id": task_id,
            "conversation_id": conversation_id,
            "user_message_id": user_message_id,
            "assistant_message_id": assistant_message_id,
            "organization_id": organization_id,
            "attached_file_count": len(attached_file_ids),
        }
    finally:
        await cleanup_checkpointer_pool(checkpointer_pool)


@backend_worker.task(
    bind=True,
    name=WorkerTaskName.RUN_ADMIN_CHAT.value,
    max_retries=TASK_MAX_RETRIES,
)
def run_admin_chat_task(
    self: Any,
    *,
    session_id: str,
    admin_user_id: str,
    user_message_id: str,
    assistant_message_id: str,
    organization_id: str,
    window_start: str | None = None,
    window_end: str | None = None,
) -> None:
    """Future admin chat side-panel agent entrypoint."""
    _raise_scaffold_not_implemented(
        WorkerTaskName.RUN_ADMIN_CHAT,
        task_id=self.request.id,
        session_id=session_id,
        admin_user_id=admin_user_id,
        user_message_id=user_message_id,
        assistant_message_id=assistant_message_id,
        organization_id=organization_id,
        has_window=window_start is not None or window_end is not None,
    )


@backend_worker.task(
    bind=True,
    name=WorkerTaskName.EXTRACT_CONVERSATION_FILE.value,
    max_retries=TASK_MAX_RETRIES,
)
def extract_conversation_file_task(
    self: Any,
    *,
    conversation_id: str,
    file_id: str,
    athlete_user_id: str,
    organization_id: str,
) -> None:
    """Future conversation-scoped file extraction entrypoint."""
    _raise_scaffold_not_implemented(
        WorkerTaskName.EXTRACT_CONVERSATION_FILE,
        task_id=self.request.id,
        conversation_id=conversation_id,
        file_id=file_id,
        athlete_user_id=athlete_user_id,
        organization_id=organization_id,
    )


@backend_worker.task(
    bind=True,
    name=WorkerTaskName.GENERATE_DASHBOARD_INSIGHTS.value,
    max_retries=TASK_MAX_RETRIES,
)
def generate_dashboard_insights_task(
    self: Any,
    *,
    run_id: str,
    organization_id: str,
    window_start: str,
    window_end: str,
    triggered_by_user_id: str | None = None,
) -> None:
    """Future dashboard insight generation entrypoint."""
    _raise_scaffold_not_implemented(
        WorkerTaskName.GENERATE_DASHBOARD_INSIGHTS,
        task_id=self.request.id,
        run_id=run_id,
        organization_id=organization_id,
        triggered_by_user_id=triggered_by_user_id,
        window_start=window_start,
        window_end=window_end,
    )


@backend_worker.task(
    bind=True,
    name=WorkerTaskName.PRUNE_CHECKPOINTS.value,
    max_retries=TASK_MAX_RETRIES,
)
def prune_checkpoints_task(self: Any, *, retention_days: int | None = None) -> None:
    """Future LangGraph checkpoint pruning entrypoint."""
    _raise_scaffold_not_implemented(
        WorkerTaskName.PRUNE_CHECKPOINTS,
        task_id=self.request.id,
        retention_days=retention_days,
    )


@backend_worker.task(name=WorkerTaskName.HEALTH_CHECK.value)
def worker_health_check() -> dict[str, str]:
    """Return a lightweight worker health payload."""
    logger.info("backend_worker_health_check")
    return {"status": "ok"}
