"""Typed event contract for agent response streams."""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import UTC, datetime
from enum import StrEnum
from typing import Any, TypeAlias, cast

from pydantic import BaseModel, Field, field_validator

JsonValue: TypeAlias = Any


class AgentStreamEventType(StrEnum):
    """Agent stream event types shared by workers and HTTP stream endpoints."""

    CHUNK = "chunk"
    PROGRESS = "progress"
    COMPLETE = "complete"
    ERROR = "error"


class AgentStreamEvent(BaseModel):
    """JSON-safe event stored in a task-scoped Valkey stream."""

    task_id: str = Field(min_length=1)
    event_type: AgentStreamEventType
    data: dict[str, JsonValue] = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))

    @field_validator("data")
    @classmethod
    def validate_json_safe(cls, value: dict[str, JsonValue]) -> dict[str, JsonValue]:
        """Reject payloads that cannot be serialized to JSON."""
        json.dumps(value)
        return value

    @property
    def is_terminal(self) -> bool:
        """Whether this event should close a stream consumer."""
        return self.event_type in {
            AgentStreamEventType.COMPLETE,
            AgentStreamEventType.ERROR,
        }

    def to_stream_fields(self) -> dict[str, str]:
        """Serialize the event for Redis Streams field storage."""
        return {
            "task_id": self.task_id,
            "event_type": self.event_type.value,
            "data": json.dumps(self.data, separators=(",", ":")),
            "created_at": self.created_at.isoformat(),
        }

    @classmethod
    def from_stream_fields(cls, fields: dict[str, str | bytes]) -> "AgentStreamEvent":
        """Deserialize a Redis Streams field mapping into an event."""
        decoded = {_decode(key): _decode(value) for key, value in fields.items()}
        return cls(
            task_id=decoded["task_id"],
            event_type=AgentStreamEventType(decoded["event_type"]),
            data=cast(dict[str, JsonValue], json.loads(decoded["data"])),
            created_at=datetime.fromisoformat(decoded["created_at"]),
        )


@dataclass(frozen=True, slots=True)
class AgentStreamRecord:
    """One stored stream record plus its Valkey stream ID."""

    stream_id: str
    event: AgentStreamEvent


def _decode(value: str | bytes) -> str:
    if isinstance(value, bytes):
        return value.decode("utf-8")
    return value
