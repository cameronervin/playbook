"""Celery task registration for backend async workflows."""

from __future__ import annotations

from typing import Any
from uuid import UUID

import structlog
from celery.signals import worker_ready

from app.agents.executors.admin_chat_executor import AdminChatExecutor
from app.agents.executors.athlete_chat_executor import AthleteChatExecutor
from app.agents.executors.dashboard_insights_executor import DashboardInsightsExecutor
from app.agents.graph_provider import AgentGraphProvider, AgentGraphProviderCache
from app.core.config import get_settings
from app.infrastructure.knowledgebase import get_kb_provider
from app.infrastructure.llm import get_llm_provider
from app.infrastructure.storage import get_storage_provider
from app.infrastructure.streaming import get_agent_stream_provider
from app.repositories.analytics import DashboardInsightRunRepository
from app.services.admin_analytics import resolve_analytics_window
from app.services.agent_stream_service import AgentStreamService
from app.services.dashboard_insights import DashboardInsightService
from app.services.kb_ingest_outbox import KbIngestOutboxService
from app.services.upload_reconciliation_service import (
    UploadRequestReconciliationService,
)
from app.workers.app import backend_worker, get_worker_checkpointer, run_async
from app.workers.queues import WorkerTaskName
from app.workers.scheduling import (
    MAINTENANCE_STARTUP_EXPIRES_SECONDS,
    expires_for_countdown,
)
from app.workers.session import worker_db_session

logger = structlog.get_logger(__name__)
TASK_MAX_RETRIES = backend_worker.conf.playbook_task_max_retries
DEFAULT_OUTBOX_DRAIN_LIMIT = 25
DEFAULT_UPLOAD_RECONCILE_LIMIT = 100
_agent_graph_provider_cache = AgentGraphProviderCache()


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
    try:
        settings = get_settings()
        checkpointer = await get_worker_checkpointer(settings)
        async with worker_db_session(settings) as session:
            llm_provider = get_llm_provider(app_settings=settings)
            chat_model = llm_provider.get_chat_model()
            title_model = llm_provider.get_title_model()
            executor = AthleteChatExecutor(
                session=session,
                chat_model=chat_model,
                title_model=title_model,
                knowledgebase_provider=get_kb_provider(app_settings=settings),
                stream_service=stream_service,
                settings=settings,
                checkpointer=checkpointer,
                graph_provider=_get_agent_graph_provider(
                    settings=settings,
                    chat_model=chat_model,
                    title_model=title_model,
                    checkpointer=checkpointer,
                ),
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


def _get_agent_graph_provider(
    *,
    settings: Any,
    chat_model: Any,
    title_model: Any,
    checkpointer: Any,
) -> AgentGraphProvider:
    """Return a cached worker-process graph provider for current dependencies."""
    return _agent_graph_provider_cache.get_or_create(
        chat_model=chat_model,
        title_model=title_model,
        settings=settings,
        checkpointer=checkpointer,
    )


@backend_worker.task(
    bind=True,
    name=WorkerTaskName.DRAIN_KB_INGEST_OUTBOX.value,
    max_retries=TASK_MAX_RETRIES,
)
def drain_kb_ingest_outbox_task(
    self: Any,
    *,
    limit: int = DEFAULT_OUTBOX_DRAIN_LIMIT,
) -> dict[str, Any]:
    """Drain verified direct-upload ingest handoff rows."""
    task_id = str(self.request.id)
    logger.debug(
        "backend_worker_kb_ingest_outbox_invoked",
        task_id=task_id,
        limit=limit,
    )
    result = run_async(_drain_kb_ingest_outbox(limit=limit))
    _schedule_next_outbox_drain(
        limit=limit,
        countdown=result.get("next_countdown_seconds"),
    )
    return result


async def _drain_kb_ingest_outbox(*, limit: int) -> dict[str, Any]:
    settings = get_settings()
    async with worker_db_session(settings) as session:
        service = KbIngestOutboxService(
            session,
            storage=get_storage_provider(settings),
            kb_provider=get_kb_provider(app_settings=settings),
            settings=settings,
        )
        result = await service.drain_due(limit=limit)
        return result.to_task_payload()


def _schedule_next_outbox_drain(
    *,
    limit: int,
    countdown: int | None,
) -> None:
    if countdown is None or backend_worker.conf.task_always_eager:
        return
    expires = expires_for_countdown(countdown)
    try:
        drain_kb_ingest_outbox_task.apply_async(
            kwargs={"limit": limit},
            countdown=countdown,
            expires=expires,
            retry=False,
        )
        logger.info(
            "kb_ingest_outbox_rescheduled",
            limit=limit,
            countdown=countdown,
            expires=expires,
        )
    except Exception as exc:  # noqa: BLE001
        logger.warning(
            "kb_ingest_outbox_reschedule_failed",
            error_type=type(exc).__name__,
        )


@backend_worker.task(
    bind=True,
    name=WorkerTaskName.RECONCILE_UPLOAD_REQUESTS.value,
    max_retries=TASK_MAX_RETRIES,
)
def reconcile_upload_requests_task(
    self: Any,
    *,
    limit: int = DEFAULT_UPLOAD_RECONCILE_LIMIT,
) -> dict[str, Any]:
    """Expire stale direct-upload requests and clean known orphan objects."""
    task_id = str(self.request.id)
    logger.debug(
        "backend_worker_upload_reconciliation_invoked",
        task_id=task_id,
        limit=limit,
    )
    result = run_async(_reconcile_upload_requests(limit=limit))
    _schedule_next_upload_reconciliation(
        limit=limit,
        countdown=result.get("next_countdown_seconds"),
    )
    return result


async def _reconcile_upload_requests(*, limit: int) -> dict[str, Any]:
    settings = get_settings()
    async with worker_db_session(settings) as session:
        service = UploadRequestReconciliationService(
            session,
            storage=get_storage_provider(settings),
        )
        result = await service.reconcile_expired(limit=limit)
        return result.to_task_payload()


def _schedule_next_upload_reconciliation(
    *,
    limit: int,
    countdown: int | None,
) -> None:
    if countdown is None or backend_worker.conf.task_always_eager:
        return
    expires = expires_for_countdown(countdown)
    try:
        reconcile_upload_requests_task.apply_async(
            kwargs={"limit": limit},
            countdown=countdown,
            expires=expires,
            retry=False,
        )
        logger.info(
            "upload_reconciliation_rescheduled",
            limit=limit,
            countdown=countdown,
            expires=expires,
        )
    except Exception as exc:  # noqa: BLE001
        logger.warning(
            "upload_reconciliation_reschedule_failed",
            error_type=type(exc).__name__,
        )


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
) -> dict[str, Any]:
    """Execute the admin chat agent for one persisted admin question."""
    task_id = str(self.request.id)
    logger.info(
        "backend_worker_admin_chat_invoked",
        task_id=self.request.id,
        session_id=session_id,
        admin_user_id=admin_user_id,
        user_message_id=user_message_id,
        assistant_message_id=assistant_message_id,
        organization_id=organization_id,
        has_window=window_start is not None or window_end is not None,
    )
    return run_async(
        _run_admin_chat_agent(
            task_id=task_id,
            session_id=session_id,
            admin_user_id=admin_user_id,
            user_message_id=user_message_id,
            assistant_message_id=assistant_message_id,
            organization_id=organization_id,
            window_start=window_start,
            window_end=window_end,
        )
    )


async def _run_admin_chat_agent(
    *,
    task_id: str,
    session_id: str,
    admin_user_id: str,
    user_message_id: str,
    assistant_message_id: str,
    organization_id: str,
    window_start: str | None,
    window_end: str | None,
) -> dict[str, Any]:
    stream_service = AgentStreamService(get_agent_stream_provider())
    settings = get_settings()
    resolved_window_start = window_start
    resolved_window_end = window_end
    if resolved_window_start is None or resolved_window_end is None:
        start, end = resolve_analytics_window(
            window=None,
            window_start=None,
            window_end=None,
            settings=settings,
        )
        resolved_window_start = start.isoformat()
        resolved_window_end = end.isoformat()
    try:
        checkpointer = await get_worker_checkpointer(settings)
        async with worker_db_session(settings) as session:
            llm_provider = get_llm_provider(app_settings=settings)
            chat_model = llm_provider.get_chat_model()
            title_model = llm_provider.get_title_model()
            executor = AdminChatExecutor(
                session=session,
                chat_model=chat_model,
                stream_service=stream_service,
                settings=settings,
                checkpointer=checkpointer,
                graph_provider=_get_agent_graph_provider(
                    settings=settings,
                    chat_model=chat_model,
                    title_model=title_model,
                    checkpointer=checkpointer,
                ),
            )
            return await executor.execute(
                task_id=task_id,
                session_id=UUID(session_id),
                admin_user_id=UUID(admin_user_id),
                user_message_id=UUID(user_message_id),
                assistant_message_id=UUID(assistant_message_id),
                organization_id=UUID(organization_id),
                window_start=resolved_window_start,
                window_end=resolved_window_end,
            )
    except Exception as exc:  # noqa: BLE001
        error_type = type(exc).__name__
        logger.error(
            "admin_chat_task_failed",
            task_id=task_id,
            session_id=session_id,
            assistant_message_id=assistant_message_id,
            error_type=error_type,
            exc_info=True,
        )
        try:
            async with worker_db_session(settings) as session:
                executor = AdminChatExecutor(
                    session=session,
                    chat_model=object(),  # type: ignore[arg-type]
                    stream_service=stream_service,
                    settings=settings,
                )
                await executor.mark_failed(
                    task_id=task_id,
                    assistant_message_id=UUID(assistant_message_id),
                    error_type=error_type,
                )
        except Exception as mark_exc:  # noqa: BLE001
            logger.error(
                "admin_chat_mark_failed_error",
                task_id=task_id,
                assistant_message_id=assistant_message_id,
                error_type=type(mark_exc).__name__,
                exc_info=True,
            )
        await stream_service.publish_error(
            task_id,
            message="Admin chat generation failed.",
            code="agent_failed",
            metadata={
                "session_id": session_id,
                "assistant_message_id": assistant_message_id,
                "error_type": error_type,
            },
        )
        return {
            "status": "failed",
            "code": "agent_failed",
            "task_id": task_id,
            "session_id": session_id,
            "user_message_id": user_message_id,
            "assistant_message_id": assistant_message_id,
            "organization_id": organization_id,
            "error_type": error_type,
        }


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
) -> dict[str, Any]:
    """Execute dashboard insight generation for one persisted run."""
    task_id = str(self.request.id)
    logger.info(
        "backend_worker_dashboard_insights_invoked",
        task_id=task_id,
        run_id=run_id,
        organization_id=organization_id,
    )
    return run_async(
        _generate_dashboard_insights(
            task_id=task_id,
            run_id=run_id,
            organization_id=organization_id,
        )
    )


async def _generate_dashboard_insights(
    *,
    task_id: str,
    run_id: str,
    organization_id: str,
) -> dict[str, Any]:
    settings = get_settings()
    try:
        checkpointer = await get_worker_checkpointer(settings)
        async with worker_db_session(settings) as session:
            llm_provider = get_llm_provider(app_settings=settings)
            chat_model = llm_provider.get_chat_model()
            title_model = llm_provider.get_title_model()
            executor = DashboardInsightsExecutor(
                session=session,
                chat_model=chat_model,
                settings=settings,
                checkpointer=checkpointer,
                graph_provider=_get_agent_graph_provider(
                    settings=settings,
                    chat_model=chat_model,
                    title_model=title_model,
                    checkpointer=checkpointer,
                ),
            )
            return await executor.execute(
                task_id=task_id,
                run_id=UUID(run_id),
                organization_id=UUID(organization_id),
            )
    except Exception as exc:  # noqa: BLE001
        error_type = type(exc).__name__
        logger.error(
            "dashboard_insights_task_failed",
            task_id=task_id,
            run_id=run_id,
            organization_id=organization_id,
            error_type=error_type,
            exc_info=True,
        )
        await _mark_dashboard_insights_failed(
            task_id=task_id,
            run_id=run_id,
            organization_id=organization_id,
            error_type=error_type,
        )
        return {
            "status": "failed",
            "code": "agent_failed",
            "task_id": task_id,
            "run_id": run_id,
            "organization_id": organization_id,
            "error_type": error_type,
        }


async def _mark_dashboard_insights_failed(
    *,
    task_id: str,
    run_id: str,
    organization_id: str,
    error_type: str,
) -> None:
    try:
        async with worker_db_session(get_settings()) as session:
            run_repo = DashboardInsightRunRepository(session)
            run = await run_repo.get_for_organization(
                organization_id=UUID(organization_id),
                run_id=UUID(run_id),
            )
            if run is None:
                logger.warning(
                    "dashboard_insights_failed_run_missing",
                    task_id=task_id,
                    run_id=run_id,
                    organization_id=organization_id,
                )
                return
            await run_repo.update_status(
                run,
                status="failed",
                error_message=error_type,
            )
            await session.commit()
    except Exception as mark_exc:  # noqa: BLE001
        logger.error(
            "dashboard_insights_mark_failed_error",
            task_id=task_id,
            run_id=run_id,
            organization_id=organization_id,
            error_type=type(mark_exc).__name__,
            exc_info=True,
        )


@backend_worker.task(
    bind=True,
    name=WorkerTaskName.SCHEDULE_NIGHTLY_DASHBOARD_INSIGHTS.value,
    max_retries=TASK_MAX_RETRIES,
)
def schedule_nightly_dashboard_insights_task(self: Any) -> dict[str, Any]:
    """Create and enqueue nightly dashboard insight runs."""
    task_id = str(self.request.id)
    logger.info("backend_worker_nightly_dashboard_insights_invoked", task_id=task_id)
    return run_async(_schedule_nightly_dashboard_insights())


async def _schedule_nightly_dashboard_insights() -> dict[str, Any]:
    settings = get_settings()
    async with worker_db_session(settings) as session:
        service = DashboardInsightService(session, settings=settings)
        result = await service.schedule_nightly_runs()
        return result.to_payload()


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


@worker_ready.connect
def schedule_kb_ingest_outbox_startup_drain(**_: Any) -> None:
    """Kick durable ingest handoff when a backend worker starts."""
    if backend_worker.conf.task_always_eager:
        return
    try:
        drain_kb_ingest_outbox_task.apply_async(
            kwargs={"limit": DEFAULT_OUTBOX_DRAIN_LIMIT},
            expires=MAINTENANCE_STARTUP_EXPIRES_SECONDS,
            retry=False,
        )
    except Exception as exc:  # noqa: BLE001
        logger.warning(
            "kb_ingest_outbox_startup_dispatch_failed",
            error_type=type(exc).__name__,
        )


@worker_ready.connect
def schedule_upload_reconciliation_startup(**_: Any) -> None:
    """Kick stale upload cleanup when a backend worker starts."""
    if backend_worker.conf.task_always_eager:
        return
    try:
        reconcile_upload_requests_task.apply_async(
            kwargs={"limit": DEFAULT_UPLOAD_RECONCILE_LIMIT},
            expires=MAINTENANCE_STARTUP_EXPIRES_SECONDS,
            retry=False,
        )
    except Exception as exc:  # noqa: BLE001
        logger.warning(
            "upload_reconciliation_startup_dispatch_failed",
            error_type=type(exc).__name__,
        )
