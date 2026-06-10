from __future__ import annotations

import pytest


def test_backend_worker_config_declares_expected_queues() -> None:
    from app.core.config import settings
    from app.workers.app import backend_worker
    from app.workers.queues import (
        BACKEND_AGENT_QUEUE,
        BACKEND_DEFAULT_QUEUE,
        BACKEND_FILES_QUEUE,
        BACKEND_INSIGHTS_QUEUE,
        BACKEND_MAINTENANCE_QUEUE,
    )

    declared_queues = {queue.name for queue in backend_worker.conf.task_queues}

    assert backend_worker.conf.broker_url == settings.CELERY_BROKER_URL
    assert backend_worker.conf.result_backend == settings.CELERY_RESULT_BACKEND
    assert backend_worker.conf.task_default_queue == BACKEND_DEFAULT_QUEUE
    assert declared_queues == {
        BACKEND_AGENT_QUEUE,
        BACKEND_DEFAULT_QUEUE,
        BACKEND_FILES_QUEUE,
        BACKEND_INSIGHTS_QUEUE,
        BACKEND_MAINTENANCE_QUEUE,
    }
    assert backend_worker.conf.task_serializer == "json"
    assert backend_worker.conf.result_serializer == "json"
    assert backend_worker.conf.accept_content == ["json"]
    assert backend_worker.conf.task_acks_late is True
    assert backend_worker.conf.task_reject_on_worker_lost is True
    assert backend_worker.conf.worker_prefetch_multiplier == 1


def test_backend_worker_registers_and_routes_named_tasks() -> None:
    from app.workers.app import backend_worker
    from app.workers.queues import (
        BACKEND_AGENT_QUEUE,
        BACKEND_FILES_QUEUE,
        BACKEND_INSIGHTS_QUEUE,
        BACKEND_MAINTENANCE_QUEUE,
        TASK_ROUTES,
        WorkerTaskName,
    )

    expected_routes = {
        WorkerTaskName.RUN_ATHLETE_CHAT: BACKEND_AGENT_QUEUE,
        WorkerTaskName.RUN_ADMIN_CHAT: BACKEND_AGENT_QUEUE,
        WorkerTaskName.EXTRACT_CONVERSATION_FILE: BACKEND_FILES_QUEUE,
        WorkerTaskName.GENERATE_DASHBOARD_INSIGHTS: BACKEND_INSIGHTS_QUEUE,
        WorkerTaskName.PRUNE_CHECKPOINTS: BACKEND_MAINTENANCE_QUEUE,
        WorkerTaskName.HEALTH_CHECK: BACKEND_MAINTENANCE_QUEUE,
    }

    for task_name, queue_name in expected_routes.items():
        assert task_name.value in backend_worker.tasks
        assert TASK_ROUTES[task_name.value]["queue"] == queue_name


def test_worker_health_check_runs_in_eager_mode() -> None:
    from app.workers.app import backend_worker
    from app.workers.tasks import worker_health_check

    previous_always_eager = backend_worker.conf.task_always_eager
    previous_eager_propagates = backend_worker.conf.task_eager_propagates
    backend_worker.conf.task_always_eager = True
    backend_worker.conf.task_eager_propagates = True
    try:
        result = worker_health_check.delay()
    finally:
        backend_worker.conf.task_always_eager = previous_always_eager
        backend_worker.conf.task_eager_propagates = previous_eager_propagates

    assert result.get(timeout=1) == {"status": "ok"}


def test_future_task_stubs_raise_not_implemented_in_eager_mode() -> None:
    from app.workers.app import backend_worker
    from app.workers.tasks import run_athlete_chat_task

    previous_always_eager = backend_worker.conf.task_always_eager
    previous_eager_propagates = backend_worker.conf.task_eager_propagates
    backend_worker.conf.task_always_eager = True
    backend_worker.conf.task_eager_propagates = True
    try:
        with pytest.raises(NotImplementedError):
            run_athlete_chat_task.delay(
                conversation_id="00000000-0000-0000-0000-000000000001",
                athlete_user_id="00000000-0000-0000-0000-000000000002",
                user_message_id="00000000-0000-0000-0000-000000000003",
                assistant_message_id="00000000-0000-0000-0000-000000000004",
                organization_id="00000000-0000-0000-0000-000000000005",
                attached_file_ids=[],
            )
    finally:
        backend_worker.conf.task_always_eager = previous_always_eager
        backend_worker.conf.task_eager_propagates = previous_eager_propagates
