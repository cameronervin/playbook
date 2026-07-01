"""Celery application for Playbook backend workers.

The backend worker layer owns application-side async jobs such as streamed
agent execution, conversation file processing, dashboard insight generation,
and maintenance tasks. This module deliberately opens no broker connection at
import time; Celery connects lazily during dispatch or worker boot.
"""

from __future__ import annotations

import asyncio
import logging
import sys
import threading
from collections.abc import Coroutine
from typing import Any, TypeVar

import structlog
from celery import Celery, signals as celery_signals
from celery.schedules import crontab
from celery.signals import (
    worker_process_init,
    worker_process_shutdown,
    worker_ready,
)

from app.core.config import Settings, get_settings
from app.core.logging_config import configure_logging, install_secret_redaction_filter
from app.infrastructure.checkpointer import (
    cleanup_checkpointer_pool,
    create_checkpointer,
    create_checkpointer_pool,
)
from app.observability.agent_trace import verify_tracing_configuration
from app.observability.langfuse_init import init_langfuse, shutdown_langfuse
from app.workers.queues import (
    BACKEND_INSIGHTS_QUEUE,
    TASK_QUEUES,
    TASK_ROUTES,
    WorkerTaskName,
)

NOISY_WORKER_LOGGER_NAMES = (
    "httpx",
    "httpcore",
    "openai",
    "langchain",
    "langchain_core",
    "langchain_openai",
)

if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

settings = get_settings()


def configure_worker_logging(
    app_settings: Settings,
    *,
    logger: logging.Logger | None = None,
    loglevel: int | str | None = None,
) -> int:
    """Configure worker process logging without inheriting API debug verbosity."""
    effective_level = _resolve_worker_log_level(app_settings, loglevel)
    configure_logging(_level_name(effective_level))
    if logger is not None:
        install_secret_redaction_filter(logger)
    _quiet_noisy_worker_loggers(effective_level)
    return effective_level


def _resolve_worker_log_level(
    app_settings: Settings,
    loglevel: int | str | None,
) -> int:
    if loglevel is not None:
        return _coerce_log_level(loglevel)
    return _coerce_log_level(app_settings.CELERY_WORKER_LOG_LEVEL)


def _coerce_log_level(log_level: int | str) -> int:
    if isinstance(log_level, int):
        return log_level
    resolved = getattr(logging, log_level.upper(), logging.INFO)
    return int(resolved if isinstance(resolved, int) else logging.INFO)


def _level_name(log_level: int) -> str:
    name = logging.getLevelName(log_level)
    return name if isinstance(name, str) else "INFO"


def _quiet_noisy_worker_loggers(effective_level: int) -> None:
    if effective_level <= logging.DEBUG:
        return
    for logger_name in NOISY_WORKER_LOGGER_NAMES:
        logging.getLogger(logger_name).setLevel(logging.WARNING)


configure_worker_logging(settings)
logger = structlog.get_logger(__name__)

_ASYNC_RESULT = TypeVar("_ASYNC_RESULT")


def _beat_schedule(app_settings: Settings) -> dict[str, dict[str, Any]]:
    """Return Celery beat schedule entries for backend periodic jobs."""
    if not app_settings.DASHBOARD_INSIGHTS_NIGHTLY_ENABLED:
        return {}
    return {
        "nightly-dashboard-insights": {
            "task": WorkerTaskName.SCHEDULE_NIGHTLY_DASHBOARD_INSIGHTS.value,
            "schedule": crontab(
                hour=app_settings.DASHBOARD_INSIGHTS_NIGHTLY_HOUR_UTC,
                minute=app_settings.DASHBOARD_INSIGHTS_NIGHTLY_MINUTE_UTC,
            ),
            "options": {"queue": BACKEND_INSIGHTS_QUEUE},
        },
    }


def create_worker_app(settings: Settings) -> Celery:
    """Create the configured Celery worker app."""
    worker = Celery(
        "playbook_backend",
        broker=settings.CELERY_BROKER_URL,
        backend=settings.CELERY_RESULT_BACKEND,
    )
    worker.conf.update(
        task_default_queue="backend-default",
        task_queues=TASK_QUEUES,
        task_routes=TASK_ROUTES,
        beat_schedule=_beat_schedule(settings),
        task_serializer="json",
        result_serializer="json",
        accept_content=["json"],
        enable_utc=True,
        timezone="UTC",
        task_track_started=True,
        task_acks_late=True,
        task_reject_on_worker_lost=True,
        worker_prefetch_multiplier=1,
        task_soft_time_limit=settings.CELERY_TASK_SOFT_TIME_LIMIT,
        task_time_limit=settings.CELERY_TASK_HARD_TIME_LIMIT,
        task_default_retry_delay=settings.CELERY_TASK_RETRY_COUNTDOWN,
        worker_redirect_stdouts_level="INFO",
        playbook_worker_log_level=settings.CELERY_WORKER_LOG_LEVEL,
        playbook_task_max_retries=settings.CELERY_TASK_MAX_RETRIES,
        task_publish_retry=True,
        broker_transport_options={
            "visibility_timeout": max(settings.CELERY_TASK_HARD_TIME_LIMIT * 4, 3600),
        },
        result_backend_transport_options={
            "visibility_timeout": max(settings.CELERY_TASK_HARD_TIME_LIMIT * 4, 3600),
        },
        result_expires=86400,
        worker_max_tasks_per_child=100,
    )
    return worker


backend_worker = create_worker_app(settings)


def configure_celery_logging(
    logger: logging.Logger | None = None,
    loglevel: int | str | None = None,
    **_: Any,
) -> None:
    """Ensure Celery-managed loggers use the shared redaction filter."""
    configure_worker_logging(settings, logger=logger, loglevel=loglevel)


for _signal_name in ("after_setup_logger", "after_setup_task_logger"):
    _signal = getattr(celery_signals, _signal_name, None)
    if _signal is not None:
        _signal.connect(configure_celery_logging)

_worker_loop: asyncio.AbstractEventLoop | None = None
_worker_loop_owner_thread: int | None = None
_worker_resources_initialized = False
_worker_checkpointer_pool: Any | None = None
_worker_checkpointer: Any | None = None


def get_worker_loop() -> asyncio.AbstractEventLoop:
    """Return the persistent event loop created during worker initialization."""
    if _worker_loop is None:
        raise RuntimeError("Backend worker resources have not been initialized")
    return _worker_loop


def run_async(coro: Coroutine[Any, Any, _ASYNC_RESULT]) -> _ASYNC_RESULT:
    """Run an async operation from a Celery task.

    Prefork and solo workers can reuse the process-level loop initialized by
    Celery signals. Threaded pools receive a fresh loop per call because an
    event loop cannot be safely re-entered from sibling threads.
    """
    if _worker_loop is None:
        return asyncio.run(coro)

    if threading.get_ident() != _worker_loop_owner_thread:
        return asyncio.run(coro)

    if _worker_loop.is_running() or _worker_loop.is_closed():
        return asyncio.run(coro)

    try:
        return _worker_loop.run_until_complete(coro)
    except RuntimeError as exc:
        if "already running" in str(exc) or "different thread" in str(exc):
            return asyncio.run(coro)
        raise


async def get_worker_checkpointer(app_settings: Settings) -> Any:
    """Return the worker-process LangGraph checkpointer."""
    global _worker_checkpointer_pool, _worker_checkpointer

    if _worker_checkpointer is None:
        _worker_checkpointer_pool = await create_checkpointer_pool(app_settings)
        _worker_checkpointer = await create_checkpointer(_worker_checkpointer_pool)
        logger.info("backend_worker_checkpointer_initialised")
    return _worker_checkpointer


async def cleanup_worker_checkpointer() -> None:
    """Close the worker-process LangGraph checkpointer pool."""
    global _worker_checkpointer_pool, _worker_checkpointer

    await cleanup_checkpointer_pool(_worker_checkpointer_pool)
    _worker_checkpointer_pool = None
    _worker_checkpointer = None


@worker_process_init.connect
@worker_ready.connect
def init_worker_resources(**_: Any) -> None:
    """Initialize per-process worker resources once.

    Future tasks can hang expensive process-level resources from this hook
    without coupling them to FastAPI request startup.
    """
    global _worker_loop, _worker_loop_owner_thread, _worker_resources_initialized

    if _worker_resources_initialized:
        return

    init_langfuse(settings)
    tracing_status = verify_tracing_configuration(settings)
    logger.info("backend_worker_tracing_startup_check", **tracing_status)

    _worker_loop = asyncio.new_event_loop()
    asyncio.set_event_loop(_worker_loop)
    _worker_loop_owner_thread = threading.get_ident()
    _worker_resources_initialized = True

    logger.info(
        "backend_worker_initialised",
        thread_id=_worker_loop_owner_thread,
        queues=[queue.name for queue in TASK_QUEUES],
    )


@worker_process_shutdown.connect
def teardown_worker_resources(**_: Any) -> None:
    """Release per-process worker resources on clean shutdown."""
    global _worker_loop, _worker_loop_owner_thread, _worker_resources_initialized

    if _worker_loop is not None and not _worker_loop.is_closed():
        _worker_loop.run_until_complete(cleanup_worker_checkpointer())
        _worker_loop.close()

    _worker_loop = None
    _worker_loop_owner_thread = None
    _worker_resources_initialized = False
    shutdown_langfuse()
    logger.info("backend_worker_shutdown")


import app.workers.tasks  # noqa: E402,F401
