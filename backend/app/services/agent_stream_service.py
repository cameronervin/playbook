"""Domain-facing helpers for agent response stream events."""

from __future__ import annotations

import json
from collections.abc import AsyncIterator
from typing import Any

from app.infrastructure.streaming import (
    AgentStreamEvent,
    AgentStreamEventType,
    AgentStreamRecord,
    BaseAgentStreamProvider,
    JsonValue,
)

SUPPORTED_LANGGRAPH_CUSTOM_EVENT_TYPES = {
    event_type.value for event_type in AgentStreamEventType
}


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

    async def publish_langgraph_part(
        self,
        task_id: str,
        part: dict[str, Any],
    ) -> str | None:
        """Publish a LangGraph v2 stream part through the app event contract."""
        stream_mode = str(part.get("type", "custom"))
        data = part.get("data")

        if stream_mode == "messages":
            return await self._publish_langgraph_message_part(task_id, data)
        if stream_mode == "custom":
            return await self._publish_langgraph_custom_part(task_id, data)
        if stream_mode == "updates":
            return await self.publish_progress(
                task_id,
                status="graph_update",
                metadata={
                    "langgraph": {
                        "stream_mode": "updates",
                        "nodes": _langgraph_update_nodes(data),
                    }
                },
            )
        return await self.publish_progress(
            task_id,
            status=f"langgraph_{stream_mode}",
            metadata={"langgraph": {"stream_mode": stream_mode}},
        )

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

    async def _publish_langgraph_message_part(
        self,
        task_id: str,
        data: Any,
    ) -> str | None:
        if not isinstance(data, (list, tuple)) or len(data) != 2:
            return None

        message_chunk, metadata = data
        langgraph_metadata = _langgraph_metadata(
            "messages",
            metadata if isinstance(metadata, dict) else {},
        )
        return await self.publish_chunk(
            task_id,
            content=_message_content(message_chunk),
            metadata={"langgraph": langgraph_metadata},
        )

    async def _publish_langgraph_custom_part(
        self,
        task_id: str,
        data: Any,
    ) -> str:
        payload = dict(data) if isinstance(data, dict) else {"status": str(data)}
        raw_event_type = payload.pop("event_type", payload.get("type", None))
        event_type = (
            AgentStreamEventType(raw_event_type)
            if raw_event_type in SUPPORTED_LANGGRAPH_CUSTOM_EVENT_TYPES
            else AgentStreamEventType.PROGRESS
        )
        if raw_event_type == payload.get("type"):
            payload.pop("type", None)

        payload["metadata"] = _merge_metadata(
            payload.get("metadata"),
            {"langgraph": {"stream_mode": "custom"}},
        )
        if event_type == AgentStreamEventType.PROGRESS:
            payload.setdefault("status", "custom")
        if event_type == AgentStreamEventType.CHUNK:
            payload.setdefault("content", "")
        if event_type == AgentStreamEventType.ERROR:
            payload.setdefault("message", "Agent stream error")

        return await self._publish(task_id, event_type, _json_safe_dict(payload))


def format_sse_record(record: AgentStreamRecord) -> str:
    """Format one stored stream record as a Server-Sent Event frame."""
    payload = {
        "stream_id": record.stream_id,
        "task_id": record.event.task_id,
        "event_type": record.event.event_type.value,
        "created_at": record.event.created_at.isoformat(),
        "data": record.event.data,
    }
    return (
        f"id: {record.stream_id}\n"
        f"event: {record.event.event_type.value}\n"
        f"data: {json.dumps(payload, separators=(',', ':'))}\n\n"
    )


def _message_content(message_chunk: Any) -> str:
    content = getattr(message_chunk, "content", "")
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts: list[str] = []
        for block in content:
            if isinstance(block, str):
                parts.append(block)
            elif isinstance(block, dict) and isinstance(block.get("text"), str):
                parts.append(block["text"])
        return "".join(parts)
    if content is None:
        return ""
    return str(content)


def _langgraph_metadata(stream_mode: str, metadata: dict[str, Any]) -> dict[str, JsonValue]:
    safe_metadata = _json_safe_dict(metadata)
    safe_metadata["stream_mode"] = stream_mode
    return safe_metadata


def _langgraph_update_nodes(data: Any) -> list[str]:
    if not isinstance(data, dict):
        return []
    return [str(node_name) for node_name in data]


def _merge_metadata(
    existing: Any,
    addition: dict[str, JsonValue],
) -> dict[str, JsonValue]:
    merged = dict(existing) if isinstance(existing, dict) else {}
    merged.update(addition)
    return _json_safe_dict(merged)


def _json_safe_dict(value: dict[str, Any]) -> dict[str, JsonValue]:
    return {str(key): _json_safe(raw_value) for key, raw_value in value.items()}


def _json_safe(value: Any) -> JsonValue:
    try:
        json.dumps(value)
    except TypeError:
        if isinstance(value, dict):
            return _json_safe_dict(value)
        if isinstance(value, (list, tuple)):
            return [_json_safe(item) for item in value]
        return str(value)
    return value
