"""Domain-facing helpers for agent response stream events."""

from __future__ import annotations

from collections.abc import AsyncIterator

from app.infrastructure.streaming import (
    AgentStreamEvent,
    AgentStreamEventType,
    AgentStreamRecord,
    BaseAgentStreamProvider,
    JsonValue,
)


class AgentStreamService:
    """Convenience bridge between workers/routes and the streaming provider."""

    def __init__(self, provider: BaseAgentStreamProvider) -> None:
        self.provider = provider

    async def publish_chunk(
        self,
        task_id: str,
        *,
        content: str,
        metadata: dict[str, JsonValue] | None = None,
    ) -> str:
        """Publish an assistant text chunk."""
        data: dict[str, JsonValue] = {"content": content}
        if metadata is not None:
            data["metadata"] = metadata
        return await self._publish(task_id, AgentStreamEventType.CHUNK, data)

    async def publish_progress(
        self,
        task_id: str,
        *,
        status: str,
        metadata: dict[str, JsonValue] | None = None,
    ) -> str:
        """Publish an agent lifecycle/progress update."""
        data: dict[str, JsonValue] = {"status": status}
        if metadata is not None:
            data["metadata"] = metadata
        return await self._publish(task_id, AgentStreamEventType.PROGRESS, data)

    async def publish_complete(
        self,
        task_id: str,
        *,
        data: dict[str, JsonValue] | None = None,
    ) -> str:
        """Publish a terminal completion event."""
        return await self._publish(
            task_id,
            AgentStreamEventType.COMPLETE,
            data or {},
        )

    async def publish_error(
        self,
        task_id: str,
        *,
        message: str,
        code: str | None = None,
        metadata: dict[str, JsonValue] | None = None,
    ) -> str:
        """Publish a terminal error event."""
        data: dict[str, JsonValue] = {"message": message}
        if code is not None:
            data["code"] = code
        if metadata is not None:
            data["metadata"] = metadata
        return await self._publish(task_id, AgentStreamEventType.ERROR, data)

    def iter_task_events(
        self,
        task_id: str,
        *,
        after_id: str = "0-0",
    ) -> AsyncIterator[AgentStreamRecord]:
        """Yield task stream records after *after_id*."""
        return self.provider.iter_events(task_id, after_id=after_id)

    async def _publish(
        self,
        task_id: str,
        event_type: AgentStreamEventType,
        data: dict[str, JsonValue],
    ) -> str:
        event = AgentStreamEvent(
            task_id=task_id,
            event_type=event_type,
            data=data,
        )
        return await self.provider.publish_event(event)
