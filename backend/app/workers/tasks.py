"""Celery task registration for backend async workflows.

These tasks intentionally expose the names and JSON-safe payload shapes that
later Phase 2+ work will build on. Only the health check is executable today;
future-facing tasks fail loudly so accidental production dispatch is visible.
"""

from __future__ import annotations

from typing import Any

import structlog

from app.core.config import settings
from app.workers.app import backend_worker
from app.workers.queues import WorkerTaskName

logger = structlog.get_logger(__name__)


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
    max_retries=settings.CELERY_TASK_MAX_RETRIES,
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
) -> None:
    """Future athlete chat agent entrypoint."""
    _raise_scaffold_not_implemented(
        WorkerTaskName.RUN_ATHLETE_CHAT,
        task_id=self.request.id,
        conversation_id=conversation_id,
        athlete_user_id=athlete_user_id,
        user_message_id=user_message_id,
        assistant_message_id=assistant_message_id,
        organization_id=organization_id,
        attached_file_count=len(attached_file_ids or []),
    )


@backend_worker.task(
    bind=True,
    name=WorkerTaskName.RUN_ADMIN_CHAT.value,
    max_retries=settings.CELERY_TASK_MAX_RETRIES,
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
    max_retries=settings.CELERY_TASK_MAX_RETRIES,
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
    max_retries=settings.CELERY_TASK_MAX_RETRIES,
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
    max_retries=settings.CELERY_TASK_MAX_RETRIES,
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
