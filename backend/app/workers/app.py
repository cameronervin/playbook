"""Celery application for Playbook backend workers.

The backend worker layer owns application-side async jobs such as streamed
agent execution, conversation file processing, dashboard insight generation,
and maintenance tasks. This module deliberately opens no broker connection at
import time; Celery connects lazily during dispatch or worker boot.
"""

from __future__ import annotations

import asyncio
import sys
import threading
from collections.abc import Coroutine
from typing import Any, TypeVar

import structlog
from celery import Celery
from celery.signals import worker_process_init, worker_process_shutdown, worker_ready

from app.core.config import settings
from app.workers.queues import (
    TASK_QUEUES,
    TASK_ROUTES,
)

if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

logger = structlog.get_logger(__name__)

_ASYNC_RESULT = TypeVar("_ASYNC_RESULT")

backend_worker = Celery(
    "playbook_backend",
    broker=settings.CELERY_BROKER_URL,
    backend=settings.CELERY_RESULT_BACKEND,
)

backend_worker.conf.update(
    task_default_queue="backend-default",
    task_queues=TASK_QUEUES,
    task_routes=TASK_ROUTES,
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

_worker_loop: asyncio.AbstractEventLoop | None = None
_worker_loop_owner_thread: int | None = None
_worker_resources_initialized = False


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
        _worker_loop.close()

    _worker_loop = None
    _worker_loop_owner_thread = None
    _worker_resources_initialized = False
    logger.info("backend_worker_shutdown")


import app.workers.tasks  # noqa: E402,F401
