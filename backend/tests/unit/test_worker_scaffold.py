from __future__ import annotations

import asyncio
import logging
import os
import subprocess
import sys
from datetime import UTC, datetime
from types import SimpleNamespace
from uuid import uuid4

from app.core.config import Settings, get_settings
from app.infrastructure.streaming import (
    AgentStreamEventType,
    InMemoryAgentStreamProvider,
)
from app.workers import app as worker_app, tasks as worker_tasks
from app.workers.app import backend_worker, create_worker_app
from app.workers.dispatcher import (
    AdminChatTaskDispatcher,
    AdminChatTaskPayload,
    AthleteChatTaskDispatcher,
    AthleteChatTaskPayload,
    DashboardInsightsTaskDispatcher,
    DashboardInsightsTaskPayload,
    KbIngestOutboxTaskDispatcher,
    UploadRequestReconciliationTaskDispatcher,
)
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
    drain_kb_ingest_outbox_task,
    generate_dashboard_insights_task,
    reconcile_upload_requests_task,
    run_admin_chat_task,
    run_athlete_chat_task,
    schedule_nightly_dashboard_insights_task,
    worker_health_check,
)


def _settings(**overrides: object) -> Settings:
    values: dict[str, object] = {
        "DATABASE_URL": "postgresql+asyncpg://app:pass@localhost:5432/playbook",
        "SECRET_KEY": "test-secret-value-that-is-long-enough",
        "LLM_PROVIDER_MODE": "direct",
        "LLM_DIRECT_PROVIDER": "anthropic",
        "ANTHROPIC_API_KEY": "anthropic-key",
    }
    values.update(overrides)
    return Settings(_env_file=None, **values)


def test_backend_worker_config_declares_expected_queues() -> None:
    declared_queues = {queue.name for queue in backend_worker.conf.task_queues}
    settings = get_settings()

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


def test_create_worker_app_uses_supplied_settings() -> None:
    app = create_worker_app(
        _settings(
            CELERY_BROKER_URL="redis://broker.example/9",
            CELERY_RESULT_BACKEND="redis://backend.example/8",
            CELERY_TASK_SOFT_TIME_LIMIT=12,
            CELERY_TASK_HARD_TIME_LIMIT=34,
            CELERY_TASK_RETRY_COUNTDOWN=5,
        )
    )

    assert app.conf.broker_url == "redis://broker.example/9"
    assert app.conf.result_backend == "redis://backend.example/8"
    assert app.conf.task_soft_time_limit == 12
    assert app.conf.task_time_limit == 34
    assert app.conf.task_default_retry_delay == 5


def test_create_worker_app_registers_dashboard_insights_beat_schedule() -> None:
    app = create_worker_app(
        _settings(
            DASHBOARD_INSIGHTS_NIGHTLY_HOUR_UTC=4,
            DASHBOARD_INSIGHTS_NIGHTLY_MINUTE_UTC=30,
        )
    )

    entry = app.conf.beat_schedule["nightly-dashboard-insights"]

    assert entry["task"] == WorkerTaskName.SCHEDULE_NIGHTLY_DASHBOARD_INSIGHTS.value
    assert entry["options"]["queue"] == BACKEND_INSIGHTS_QUEUE
    assert str(entry["schedule"]) == "<crontab: 30 4 * * * (m/h/dM/MY/d)>"


def test_create_worker_app_omits_dashboard_insights_beat_when_disabled() -> None:
    app = create_worker_app(_settings(DASHBOARD_INSIGHTS_NIGHTLY_ENABLED=False))

    assert app.conf.beat_schedule == {}


def test_create_worker_app_separates_worker_log_level_from_app_log_level() -> None:
    app = create_worker_app(
        _settings(
            LOG_LEVEL="DEBUG",
            CELERY_WORKER_LOG_LEVEL="INFO",
        )
    )

    assert app.conf.playbook_worker_log_level == "INFO"
    assert app.conf.worker_redirect_stdouts_level == "INFO"


def test_worker_logging_prefers_celery_signal_log_level(monkeypatch) -> None:
    configured: dict[str, object] = {}

    def fake_configure_logging(log_level: str) -> None:
        configured["log_level"] = log_level

    monkeypatch.setattr(worker_app, "configure_logging", fake_configure_logging)

    effective_level = worker_app.configure_worker_logging(
        _settings(
            LOG_LEVEL="DEBUG",
            CELERY_WORKER_LOG_LEVEL="WARNING",
        ),
        loglevel=logging.INFO,
    )

    assert effective_level == logging.INFO
    assert configured["log_level"] == "INFO"


def test_worker_logging_quiets_noisy_third_party_loggers(monkeypatch) -> None:
    configured: dict[str, object] = {}

    def fake_configure_logging(log_level: str) -> None:
        configured["log_level"] = log_level

    monkeypatch.setattr(worker_app, "configure_logging", fake_configure_logging)
    original_levels = {
        name: logging.getLogger(name).level
        for name in worker_app.NOISY_WORKER_LOGGER_NAMES
    }
    try:
        worker_app.configure_worker_logging(
            _settings(CELERY_WORKER_LOG_LEVEL="INFO")
        )

        assert configured["log_level"] == "INFO"
        assert all(
            logging.getLogger(name).level == logging.WARNING
            for name in worker_app.NOISY_WORKER_LOGGER_NAMES
        )
    finally:
        for name, level in original_levels.items():
            logging.getLogger(name).setLevel(level)


def test_backend_worker_app_imports_in_fresh_process() -> None:
    env = {
        **os.environ,
        "ENVIRONMENT": "test",
        "DEBUG": "false",
        "DEV_AUTH_ENABLED": "false",
        "SECRET_KEY": "test-secret-value-that-is-long-enough",
        "OAUTH_STATE_SECRET": "test-oauth-secret-value-that-is-long-enough",
        "LLM_PROVIDER_MODE": "direct",
        "LLM_DIRECT_PROVIDER": "anthropic",
        "ANTHROPIC_API_KEY": "test-anthropic-key",
    }

    result = subprocess.run(
        [sys.executable, "-c", "import app.workers.app"],
        check=False,
        cwd=os.getcwd(),
        env=env,
        stderr=subprocess.PIPE,
        stdout=subprocess.PIPE,
        text=True,
        timeout=45,
    )

    assert result.returncode == 0, result.stderr


def test_backend_worker_registers_and_routes_named_tasks() -> None:
    expected_routes = {
        WorkerTaskName.RUN_ATHLETE_CHAT: BACKEND_AGENT_QUEUE,
        WorkerTaskName.RUN_ADMIN_CHAT: BACKEND_AGENT_QUEUE,
        WorkerTaskName.DRAIN_KB_INGEST_OUTBOX: BACKEND_FILES_QUEUE,
        WorkerTaskName.RECONCILE_UPLOAD_REQUESTS: BACKEND_MAINTENANCE_QUEUE,
        WorkerTaskName.GENERATE_DASHBOARD_INSIGHTS: BACKEND_INSIGHTS_QUEUE,
        WorkerTaskName.SCHEDULE_NIGHTLY_DASHBOARD_INSIGHTS: BACKEND_INSIGHTS_QUEUE,
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


def test_admin_chat_dispatcher_uses_explicit_task_id(monkeypatch) -> None:
    payload = AdminChatTaskPayload(
        session_id=uuid4(),
        admin_user_id=uuid4(),
        user_message_id=uuid4(),
        assistant_message_id=uuid4(),
        organization_id=uuid4(),
        window_start=datetime(2026, 6, 1, tzinfo=UTC),
        window_end=datetime(2026, 6, 8, tzinfo=UTC),
    )
    task_id = str(uuid4())
    dispatched: dict[str, object] = {}

    def fake_apply_async(*, kwargs: dict[str, object], task_id: str) -> SimpleNamespace:
        dispatched["kwargs"] = kwargs
        dispatched["task_id"] = task_id
        return SimpleNamespace(id=task_id)

    monkeypatch.setattr(run_admin_chat_task, "apply_async", fake_apply_async)

    returned_task_id = AdminChatTaskDispatcher().dispatch(
        task_id=task_id,
        payload=payload,
    )

    assert returned_task_id == task_id
    assert dispatched["task_id"] == task_id
    assert dispatched["kwargs"] == {
        "session_id": str(payload.session_id),
        "admin_user_id": str(payload.admin_user_id),
        "user_message_id": str(payload.user_message_id),
        "assistant_message_id": str(payload.assistant_message_id),
        "organization_id": str(payload.organization_id),
        "window_start": payload.window_start.isoformat(),
        "window_end": payload.window_end.isoformat(),
    }
    assert WorkerTaskName.RUN_ADMIN_CHAT.value == run_admin_chat_task.name


def test_kb_ingest_outbox_task_runs_drain_entrypoint_in_eager_mode(
    monkeypatch,
) -> None:
    async def fake_drain(*, limit: int) -> dict[str, object]:
        return {
            "status": "complete",
            "limit": limit,
            "processed": 2,
            "dispatched": 1,
            "retried": 1,
            "failed": 0,
        }

    monkeypatch.setattr(
        worker_tasks,
        "_drain_kb_ingest_outbox",
        fake_drain,
        raising=False,
    )
    previous_always_eager = backend_worker.conf.task_always_eager
    previous_eager_propagates = backend_worker.conf.task_eager_propagates
    backend_worker.conf.task_always_eager = True
    backend_worker.conf.task_eager_propagates = True
    try:
        result = drain_kb_ingest_outbox_task.delay(limit=2)
    finally:
        backend_worker.conf.task_always_eager = previous_always_eager
        backend_worker.conf.task_eager_propagates = previous_eager_propagates

    assert result.get(timeout=1) == {
        "status": "complete",
        "limit": 2,
        "processed": 2,
        "dispatched": 1,
        "retried": 1,
        "failed": 0,
    }
    assert (
        WorkerTaskName.DRAIN_KB_INGEST_OUTBOX.value
        == drain_kb_ingest_outbox_task.name
    )


def test_upload_reconciliation_task_runs_entrypoint_in_eager_mode(
    monkeypatch,
) -> None:
    async def fake_reconcile(*, limit: int) -> dict[str, object]:
        return {
            "status": "complete",
            "limit": limit,
            "processed": 3,
            "expired": 2,
            "resources_failed": 2,
            "objects_deleted": 1,
            "objects_missing": 1,
            "cleanup_failed": 0,
            "skipped": 1,
            "next_countdown_seconds": None,
        }

    monkeypatch.setattr(
        worker_tasks,
        "_reconcile_upload_requests",
        fake_reconcile,
        raising=False,
    )
    previous_always_eager = backend_worker.conf.task_always_eager
    previous_eager_propagates = backend_worker.conf.task_eager_propagates
    backend_worker.conf.task_always_eager = True
    backend_worker.conf.task_eager_propagates = True
    try:
        result = reconcile_upload_requests_task.delay(limit=3)
    finally:
        backend_worker.conf.task_always_eager = previous_always_eager
        backend_worker.conf.task_eager_propagates = previous_eager_propagates

    assert result.get(timeout=1) == {
        "status": "complete",
        "limit": 3,
        "processed": 3,
        "expired": 2,
        "resources_failed": 2,
        "objects_deleted": 1,
        "objects_missing": 1,
        "cleanup_failed": 0,
        "skipped": 1,
        "next_countdown_seconds": None,
    }
    assert (
        WorkerTaskName.RECONCILE_UPLOAD_REQUESTS.value
        == reconcile_upload_requests_task.name
    )


def test_upload_reconciliation_dispatcher_uses_countdown(monkeypatch) -> None:
    dispatched: dict[str, object] = {}

    def fake_apply_async(**options: object) -> SimpleNamespace:
        dispatched.update(options)
        return SimpleNamespace(id="reconcile-task-id")

    monkeypatch.setattr(
        reconcile_upload_requests_task,
        "apply_async",
        fake_apply_async,
    )

    task_id = UploadRequestReconciliationTaskDispatcher().dispatch(
        limit=7,
        countdown=30,
    )

    assert task_id == "reconcile-task-id"
    assert dispatched == {
        "kwargs": {"limit": 7},
        "retry": False,
        "countdown": 30,
        "expires": 90,
    }


def test_kb_ingest_outbox_dispatcher_uses_countdown_expiry(monkeypatch) -> None:
    dispatched: dict[str, object] = {}

    def fake_apply_async(**options: object) -> SimpleNamespace:
        dispatched.update(options)
        return SimpleNamespace(id="outbox-task-id")

    monkeypatch.setattr(
        drain_kb_ingest_outbox_task,
        "apply_async",
        fake_apply_async,
    )

    task_id = KbIngestOutboxTaskDispatcher().dispatch(
        limit=5,
        countdown=45,
    )

    assert task_id == "outbox-task-id"
    assert dispatched == {
        "kwargs": {"limit": 5},
        "retry": False,
        "countdown": 45,
        "expires": 105,
    }


def test_dashboard_insights_dispatcher_serializes_payload(monkeypatch) -> None:
    run_id = uuid4()
    organization_id = uuid4()
    dispatched: dict[str, object] = {}

    def fake_apply_async(*, kwargs: dict[str, object]) -> SimpleNamespace:
        dispatched["kwargs"] = kwargs
        return SimpleNamespace(id="dashboard-task-id")

    monkeypatch.setattr(
        generate_dashboard_insights_task,
        "apply_async",
        fake_apply_async,
    )

    task_id = DashboardInsightsTaskDispatcher().dispatch(
        payload=DashboardInsightsTaskPayload(
            run_id=run_id,
            organization_id=organization_id,
        )
    )

    assert task_id == "dashboard-task-id"
    assert dispatched["kwargs"] == {
        "run_id": str(run_id),
        "organization_id": str(organization_id),
    }


def test_outbox_reschedule_adds_expiry(monkeypatch) -> None:
    dispatched: dict[str, object] = {}

    def fake_apply_async(**options: object) -> SimpleNamespace:
        dispatched.update(options)
        return SimpleNamespace(id="outbox-task-id")

    monkeypatch.setattr(
        drain_kb_ingest_outbox_task,
        "apply_async",
        fake_apply_async,
    )

    worker_tasks._schedule_next_outbox_drain(limit=25, countdown=30)

    assert dispatched == {
        "kwargs": {"limit": 25},
        "countdown": 30,
        "expires": 90,
        "retry": False,
    }


def test_upload_reconciliation_reschedule_adds_expiry(monkeypatch) -> None:
    dispatched: dict[str, object] = {}

    def fake_apply_async(**options: object) -> SimpleNamespace:
        dispatched.update(options)
        return SimpleNamespace(id="reconcile-task-id")

    monkeypatch.setattr(
        reconcile_upload_requests_task,
        "apply_async",
        fake_apply_async,
    )

    worker_tasks._schedule_next_upload_reconciliation(limit=100, countdown=30)

    assert dispatched == {
        "kwargs": {"limit": 100},
        "countdown": 30,
        "expires": 90,
        "retry": False,
    }


def test_startup_maintenance_dispatches_use_short_expiry(monkeypatch) -> None:
    outbox_dispatch: dict[str, object] = {}
    reconcile_dispatch: dict[str, object] = {}

    def fake_outbox_apply_async(**options: object) -> SimpleNamespace:
        outbox_dispatch.update(options)
        return SimpleNamespace(id="outbox-task-id")

    def fake_reconcile_apply_async(**options: object) -> SimpleNamespace:
        reconcile_dispatch.update(options)
        return SimpleNamespace(id="reconcile-task-id")

    monkeypatch.setattr(
        drain_kb_ingest_outbox_task,
        "apply_async",
        fake_outbox_apply_async,
    )
    monkeypatch.setattr(
        reconcile_upload_requests_task,
        "apply_async",
        fake_reconcile_apply_async,
    )

    worker_tasks.schedule_kb_ingest_outbox_startup_drain()
    worker_tasks.schedule_upload_reconciliation_startup()

    assert outbox_dispatch == {
        "kwargs": {"limit": worker_tasks.DEFAULT_OUTBOX_DRAIN_LIMIT},
        "expires": 60,
        "retry": False,
    }
    assert reconcile_dispatch == {
        "kwargs": {"limit": worker_tasks.DEFAULT_UPLOAD_RECONCILE_LIMIT},
        "expires": 60,
        "retry": False,
    }


def test_athlete_chat_task_runs_agent_entrypoint_in_eager_mode(
    monkeypatch,
) -> None:
    provider = InMemoryAgentStreamProvider()

    async def fake_run_agent(**kwargs: object) -> dict[str, object]:
        task_id = str(kwargs["task_id"])
        stream_service = worker_tasks.AgentStreamService(provider)
        await stream_service.publish_progress(task_id, status="loading_context")
        await stream_service.publish_chunk(task_id, content="Grounded answer.")
        await stream_service.publish_complete(
            task_id,
            data={
                "assistant_message_id": kwargs["assistant_message_id"],
                "answer_type": "grounded_answer",
                "citation_count": 1,
            },
        )
        return {
            "status": "complete",
            "task_id": task_id,
            "assistant_message_id": kwargs["assistant_message_id"],
            "answer_type": "grounded_answer",
            "citation_count": 1,
        }

    monkeypatch.setattr(
        worker_tasks,
        "get_agent_stream_provider",
        lambda: provider,
        raising=False,
    )
    monkeypatch.setattr(
        worker_tasks,
        "_run_athlete_chat_agent",
        fake_run_agent,
        raising=False,
    )
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

    payload = result.get(timeout=1)
    assert payload["status"] == "complete"
    assert payload["answer_type"] == "grounded_answer"
    assert payload["citation_count"] == 1

    async def collect_records():
        return [
            record
            async for record in provider.iter_events(payload["task_id"], after_id="0-0")
        ]

    records = asyncio.run(collect_records())
    assert [record.event.event_type for record in records] == [
        AgentStreamEventType.PROGRESS,
        AgentStreamEventType.CHUNK,
        AgentStreamEventType.COMPLETE,
    ]
    assert records[0].event.data["status"] == "loading_context"
    assert records[1].event.data["content"] == "Grounded answer."
    assert records[2].event.data["answer_type"] == "grounded_answer"


def test_athlete_chat_task_failure_publishes_agent_error_in_eager_mode(
    monkeypatch,
) -> None:
    provider = InMemoryAgentStreamProvider()

    async def fake_run_agent(**kwargs: object) -> dict[str, object]:
        task_id = str(kwargs["task_id"])
        stream_service = worker_tasks.AgentStreamService(provider)
        await stream_service.publish_error(
            task_id,
            message="Athlete chat generation failed.",
            code="agent_failed",
        )
        return {
            "status": "failed",
            "code": "agent_failed",
            "task_id": task_id,
        }

    monkeypatch.setattr(
        worker_tasks,
        "get_agent_stream_provider",
        lambda: provider,
        raising=False,
    )
    monkeypatch.setattr(
        worker_tasks,
        "_run_athlete_chat_agent",
        fake_run_agent,
        raising=False,
    )
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

    payload = result.get(timeout=1)
    assert payload["status"] == "failed"
    assert payload["code"] == "agent_failed"

    async def collect_records():
        return [
            record
            async for record in provider.iter_events(payload["task_id"], after_id="0-0")
        ]

    records = asyncio.run(collect_records())
    assert [record.event.event_type for record in records] == [
        AgentStreamEventType.ERROR,
    ]
    assert records[0].event.data["code"] == "agent_failed"


def test_dashboard_insights_task_runs_entrypoint_in_eager_mode(monkeypatch) -> None:
    async def fake_generate(**kwargs: object) -> dict[str, object]:
        return {
            "status": "completed",
            "run_id": kwargs["run_id"],
            "organization_id": kwargs["organization_id"],
        }

    monkeypatch.setattr(
        worker_tasks,
        "_generate_dashboard_insights",
        fake_generate,
        raising=False,
    )
    previous_always_eager = backend_worker.conf.task_always_eager
    previous_eager_propagates = backend_worker.conf.task_eager_propagates
    backend_worker.conf.task_always_eager = True
    backend_worker.conf.task_eager_propagates = True
    try:
        result = generate_dashboard_insights_task.delay(
            run_id="00000000-0000-0000-0000-000000000001",
            organization_id="00000000-0000-0000-0000-000000000002",
        )
    finally:
        backend_worker.conf.task_always_eager = previous_always_eager
        backend_worker.conf.task_eager_propagates = previous_eager_propagates

    assert result.get(timeout=1) == {
        "status": "completed",
        "run_id": "00000000-0000-0000-0000-000000000001",
        "organization_id": "00000000-0000-0000-0000-000000000002",
    }


def test_nightly_dashboard_insights_task_runs_entrypoint_in_eager_mode(
    monkeypatch,
) -> None:
    async def fake_schedule() -> dict[str, object]:
        return {"status": "scheduled", "created": 2, "dispatched": 2}

    monkeypatch.setattr(
        worker_tasks,
        "_schedule_nightly_dashboard_insights",
        fake_schedule,
        raising=False,
    )
    previous_always_eager = backend_worker.conf.task_always_eager
    previous_eager_propagates = backend_worker.conf.task_eager_propagates
    backend_worker.conf.task_always_eager = True
    backend_worker.conf.task_eager_propagates = True
    try:
        result = schedule_nightly_dashboard_insights_task.delay()
    finally:
        backend_worker.conf.task_always_eager = previous_always_eager
        backend_worker.conf.task_eager_propagates = previous_eager_propagates

    assert result.get(timeout=1) == {
        "status": "scheduled",
        "created": 2,
        "dispatched": 2,
    }


def test_admin_chat_task_runs_entrypoint_in_eager_mode(monkeypatch) -> None:
    async def fake_run_agent(**kwargs: object) -> dict[str, object]:
        return {
            "status": "complete",
            "task_id": kwargs["task_id"],
            "session_id": kwargs["session_id"],
            "assistant_message_id": kwargs["assistant_message_id"],
            "answer_type": "analytics_answer",
        }

    monkeypatch.setattr(
        worker_tasks,
        "_run_admin_chat_agent",
        fake_run_agent,
        raising=False,
    )
    previous_always_eager = backend_worker.conf.task_always_eager
    previous_eager_propagates = backend_worker.conf.task_eager_propagates
    backend_worker.conf.task_always_eager = True
    backend_worker.conf.task_eager_propagates = True
    try:
        result = run_admin_chat_task.delay(
            session_id="00000000-0000-0000-0000-000000000001",
            admin_user_id="00000000-0000-0000-0000-000000000002",
            user_message_id="00000000-0000-0000-0000-000000000003",
            assistant_message_id="00000000-0000-0000-0000-000000000004",
            organization_id="00000000-0000-0000-0000-000000000005",
            window_start="2026-06-01T00:00:00+00:00",
            window_end="2026-06-08T00:00:00+00:00",
        )
    finally:
        backend_worker.conf.task_always_eager = previous_always_eager
        backend_worker.conf.task_eager_propagates = previous_eager_propagates

    payload = result.get(timeout=1)
    assert payload["status"] == "complete"
    assert payload["session_id"] == "00000000-0000-0000-0000-000000000001"
    assert payload["assistant_message_id"] == "00000000-0000-0000-0000-000000000004"
    assert payload["answer_type"] == "analytics_answer"
