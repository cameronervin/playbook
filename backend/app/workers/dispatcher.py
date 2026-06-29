"""Dispatch helpers for backend Celery tasks."""

from __future__ import annotations

from dataclasses import dataclass, field
from uuid import UUID

from app.workers.scheduling import expires_for_countdown


@dataclass(frozen=True)
class AthleteChatTaskPayload:
    """ID-only athlete chat task payload safe to send through the broker."""

    conversation_id: UUID
    athlete_user_id: UUID
    user_message_id: UUID
    assistant_message_id: UUID
    organization_id: UUID
    attached_file_ids: list[UUID] = field(default_factory=list)

    def to_kwargs(self) -> dict[str, str | list[str]]:
        """Return JSON-safe task kwargs."""
        return {
            "conversation_id": str(self.conversation_id),
            "athlete_user_id": str(self.athlete_user_id),
            "user_message_id": str(self.user_message_id),
            "assistant_message_id": str(self.assistant_message_id),
            "organization_id": str(self.organization_id),
            "attached_file_ids": [
                str(file_id) for file_id in self.attached_file_ids
            ],
        }


class AthleteChatTaskDispatcher:
    """Dispatch athlete chat work to the backend Celery worker."""

    def dispatch(self, *, task_id: str, payload: AthleteChatTaskPayload) -> str:
        """Enqueue athlete chat work and return the Celery task id."""
        from app.workers.tasks import run_athlete_chat_task  # noqa: PLC0415

        result = run_athlete_chat_task.apply_async(
            kwargs=payload.to_kwargs(),
            task_id=task_id,
        )
        return str(result.id)


@dataclass(frozen=True)
class DashboardInsightsTaskPayload:
    """ID-only dashboard insights payload safe to send through the broker."""

    run_id: UUID
    organization_id: UUID

    def to_kwargs(self) -> dict[str, str]:
        """Return JSON-safe task kwargs."""
        return {
            "run_id": str(self.run_id),
            "organization_id": str(self.organization_id),
        }


class DashboardInsightsTaskDispatcher:
    """Dispatch dashboard insight generation to the backend worker."""

    def dispatch(self, *, payload: DashboardInsightsTaskPayload) -> str:
        """Enqueue dashboard insight generation and return the Celery task id."""
        from app.workers.tasks import generate_dashboard_insights_task  # noqa: PLC0415

        result = generate_dashboard_insights_task.apply_async(
            kwargs=payload.to_kwargs(),
        )
        return str(result.id)


class KbIngestOutboxTaskDispatcher:
    """Dispatch durable KB ingest outbox drain work to the backend worker."""

    def dispatch(self, *, limit: int = 25, countdown: int | None = None) -> str:
        """Enqueue outbox draining and return the Celery task id."""
        from app.workers.tasks import drain_kb_ingest_outbox_task  # noqa: PLC0415

        options: dict[str, object] = {
            "kwargs": {"limit": limit},
            "retry": False,
        }
        if countdown is not None:
            options["countdown"] = countdown
            options["expires"] = expires_for_countdown(countdown)
        result = drain_kb_ingest_outbox_task.apply_async(**options)
        return str(result.id)


class UploadRequestReconciliationTaskDispatcher:
    """Dispatch direct-upload reconciliation work to the backend worker."""

    def dispatch(self, *, limit: int = 100, countdown: int | None = None) -> str:
        """Enqueue expired direct-upload reconciliation and return the task id."""
        from app.workers.tasks import reconcile_upload_requests_task  # noqa: PLC0415

        options: dict[str, object] = {
            "kwargs": {"limit": limit},
            "retry": False,
        }
        if countdown is not None:
            options["countdown"] = countdown
            options["expires"] = expires_for_countdown(countdown)
        result = reconcile_upload_requests_task.apply_async(**options)
        return str(result.id)
