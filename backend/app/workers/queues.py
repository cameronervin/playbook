"""Queue names and routing for backend Celery workers."""

from __future__ import annotations

from enum import StrEnum

from kombu import Queue

BACKEND_DEFAULT_QUEUE = "backend-default"
BACKEND_AGENT_QUEUE = "backend-agent"
BACKEND_FILES_QUEUE = "backend-files"
BACKEND_INSIGHTS_QUEUE = "backend-insights"
BACKEND_MAINTENANCE_QUEUE = "backend-maintenance"


class WorkerTaskName(StrEnum):
    """Registered task names for the backend worker layer."""

    RUN_ATHLETE_CHAT = "app.workers.tasks.run_athlete_chat_task"
    RUN_ADMIN_CHAT = "app.workers.tasks.run_admin_chat_task"
    DRAIN_KB_INGEST_OUTBOX = "app.workers.tasks.drain_kb_ingest_outbox_task"
    RECONCILE_UPLOAD_REQUESTS = "app.workers.tasks.reconcile_upload_requests_task"
    GENERATE_DASHBOARD_INSIGHTS = "app.workers.tasks.generate_dashboard_insights_task"
    SCHEDULE_NIGHTLY_DASHBOARD_INSIGHTS = (
        "app.workers.tasks.schedule_nightly_dashboard_insights_task"
    )
    PRUNE_CHECKPOINTS = "app.workers.tasks.prune_checkpoints_task"
    HEALTH_CHECK = "app.workers.tasks.worker_health_check"


TASK_QUEUES = (
    Queue(BACKEND_DEFAULT_QUEUE),
    Queue(BACKEND_AGENT_QUEUE),
    Queue(BACKEND_FILES_QUEUE),
    Queue(BACKEND_INSIGHTS_QUEUE),
    Queue(BACKEND_MAINTENANCE_QUEUE),
)

TASK_ROUTES: dict[str, dict[str, str]] = {
    WorkerTaskName.RUN_ATHLETE_CHAT.value: {"queue": BACKEND_AGENT_QUEUE},
    WorkerTaskName.RUN_ADMIN_CHAT.value: {"queue": BACKEND_AGENT_QUEUE},
    WorkerTaskName.DRAIN_KB_INGEST_OUTBOX.value: {"queue": BACKEND_FILES_QUEUE},
    WorkerTaskName.RECONCILE_UPLOAD_REQUESTS.value: {
        "queue": BACKEND_MAINTENANCE_QUEUE,
    },
    WorkerTaskName.GENERATE_DASHBOARD_INSIGHTS.value: {
        "queue": BACKEND_INSIGHTS_QUEUE,
    },
    WorkerTaskName.SCHEDULE_NIGHTLY_DASHBOARD_INSIGHTS.value: {
        "queue": BACKEND_INSIGHTS_QUEUE,
    },
    WorkerTaskName.PRUNE_CHECKPOINTS.value: {"queue": BACKEND_MAINTENANCE_QUEUE},
    WorkerTaskName.HEALTH_CHECK.value: {"queue": BACKEND_MAINTENANCE_QUEUE},
    "app.workers.tasks.*": {"queue": BACKEND_DEFAULT_QUEUE},
}
