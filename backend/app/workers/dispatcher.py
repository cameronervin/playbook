"""Dispatch helpers for backend Celery tasks."""

from __future__ import annotations

from dataclasses import dataclass, field
from uuid import UUID

from app.workers.tasks import run_athlete_chat_task


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
        result = run_athlete_chat_task.apply_async(
            kwargs=payload.to_kwargs(),
            task_id=task_id,
        )
        return str(result.id)
