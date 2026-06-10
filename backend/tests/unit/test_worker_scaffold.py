from __future__ import annotations

from types import SimpleNamespace
from uuid import uuid4

import pytest

from app.core.config import settings
from app.workers.app import backend_worker
from app.workers.dispatcher import AthleteChatTaskDispatcher, AthleteChatTaskPayload
from app.workers.queues import (
    BACKEND_AGENT_QUEUE,
    BACKEND_DEFAULT_QUEUE,
    BACKEND_FILES_QUEUE,
    BACKEND_INSIGHTS_QUEUE,
    BACKEND_MAINTENANCE_QUEUE,
    TASK_ROUTES,
    WorkerTaskName,
)
from app.workers.tasks import (
    run_admin_chat_task,
    run_athlete_chat_task,
    worker_health_check,
)


def test_backend_worker_config_declares_expected_queues() -> None:
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


def test_athlete_chat_dispatcher_uses_explicit_task_id(monkeypatch) -> None:
    payload = AthleteChatTaskPayload(
        conversation_id=uuid4(),
        athlete_user_id=uuid4(),
        user_message_id=uuid4(),
        assistant_message_id=uuid4(),
        organization_id=uuid4(),
        attached_file_ids=[uuid4()],
    )
    task_id = str(uuid4())
    dispatched: dict[str, object] = {}

    def fake_apply_async(*, kwargs: dict[str, object], task_id: str) -> SimpleNamespace:
        dispatched["kwargs"] = kwargs
        dispatched["task_id"] = task_id
        return SimpleNamespace(id=task_id)

    monkeypatch.setattr(run_athlete_chat_task, "apply_async", fake_apply_async)

    returned_task_id = AthleteChatTaskDispatcher().dispatch(
        task_id=task_id,
        payload=payload,
    )

    assert returned_task_id == task_id
    assert dispatched["task_id"] == task_id
    assert dispatched["kwargs"] == {
        "conversation_id": str(payload.conversation_id),
        "athlete_user_id": str(payload.athlete_user_id),
        "user_message_id": str(payload.user_message_id),
        "assistant_message_id": str(payload.assistant_message_id),
        "organization_id": str(payload.organization_id),
        "attached_file_ids": [str(payload.attached_file_ids[0])],
    }
    assert WorkerTaskName.RUN_ATHLETE_CHAT.value == run_athlete_chat_task.name


def test_athlete_chat_task_stub_returns_scaffold_payload_in_eager_mode() -> None:
    previous_always_eager = backend_worker.conf.task_always_eager
    previous_eager_propagates = backend_worker.conf.task_eager_propagates
    backend_worker.conf.task_always_eager = True
    backend_worker.conf.task_eager_propagates = True
    try:
        result = run_athlete_chat_task.delay(
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

    assert result.get(timeout=1)["status"] == "scaffolded"


def test_future_task_stubs_raise_not_implemented_in_eager_mode() -> None:
    previous_always_eager = backend_worker.conf.task_always_eager
    previous_eager_propagates = backend_worker.conf.task_eager_propagates
    backend_worker.conf.task_always_eager = True
    backend_worker.conf.task_eager_propagates = True
    try:
        with pytest.raises(NotImplementedError):
            run_admin_chat_task.delay(
                session_id="00000000-0000-0000-0000-000000000001",
                admin_user_id="00000000-0000-0000-0000-000000000002",
                user_message_id="00000000-0000-0000-0000-000000000003",
                assistant_message_id="00000000-0000-0000-0000-000000000004",
                organization_id="00000000-0000-0000-0000-000000000005",
            )
    finally:
        backend_worker.conf.task_always_eager = previous_always_eager
        backend_worker.conf.task_eager_propagates = previous_eager_propagates
