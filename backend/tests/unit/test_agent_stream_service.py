"""Unit tests for the agent stream service scaffold."""

from __future__ import annotations

import pytest

from app.infrastructure.streaming import (
    AgentStreamEventType,
    InMemoryAgentStreamProvider,
)
from app.services.agent_stream_service import AgentStreamService, format_sse_record


class _FakeMessageChunk:
    def __init__(self, content: str) -> None:
        self.content = content


@pytest.mark.asyncio
async def test_agent_stream_service_publishes_helper_events() -> None:
    provider = InMemoryAgentStreamProvider()
    service = AgentStreamService(provider)

    await service.publish_chunk("task-123", content="hello")
    await service.publish_progress("task-123", status="retrieving")
    await service.publish_error(
        "task-123",
        message="model failed",
        code="llm_error",
    )

    records = [
        record async for record in service.iter_task_events("task-123", after_id="0-0")
    ]

    assert [record.event.event_type for record in records] == [
        AgentStreamEventType.CHUNK,
        AgentStreamEventType.PROGRESS,
        AgentStreamEventType.ERROR,
    ]
    assert records[0].event.data == {"content": "hello"}
    assert records[1].event.data == {"status": "retrieving"}
    assert records[2].event.data == {
        "code": "llm_error",
        "message": "model failed",
    }


@pytest.mark.asyncio
async def test_agent_stream_service_publishes_complete_event() -> None:
    provider = InMemoryAgentStreamProvider()
    service = AgentStreamService(provider)

    stream_id = await service.publish_complete(
        "task-123",
        data={"assistant_message_id": "message-123"},
    )

    records = [
        record async for record in service.iter_task_events("task-123", after_id="0-0")
    ]

    assert stream_id == "1-0"
    assert records[0].event.event_type == AgentStreamEventType.COMPLETE
    assert records[0].event.data == {"assistant_message_id": "message-123"}


@pytest.mark.asyncio
async def test_format_sse_record_uses_stream_id_as_event_id() -> None:
    provider = InMemoryAgentStreamProvider()
    service = AgentStreamService(provider)
    await service.publish_chunk("task-123", content="hello")

    records = [
        record async for record in service.iter_task_events("task-123", after_id="0-0")
    ]

    assert format_sse_record(records[0]) == (
        'id: 1-0\n'
        'event: chunk\n'
        'data: {"stream_id":"1-0","task_id":"task-123","event_type":"chunk",'
        '"created_at":"'
        f'{records[0].event.created_at.isoformat()}",'
        '"data":{"content":"hello"}}\n\n'
    )


@pytest.mark.asyncio
async def test_agent_stream_service_maps_langgraph_messages_to_chunks() -> None:
    provider = InMemoryAgentStreamProvider()
    service = AgentStreamService(provider)

    await service.publish_langgraph_part(
        "task-123",
        {
            "type": "messages",
            "data": (
                _FakeMessageChunk("hello"),
                {"langgraph_node": "generate", "run_id": "run-1"},
            ),
        },
    )

    records = [
        record async for record in service.iter_task_events("task-123", after_id="0-0")
    ]

    assert records[0].event.event_type == AgentStreamEventType.CHUNK
    assert records[0].event.data == {
        "content": "hello",
        "metadata": {
            "langgraph": {
                "langgraph_node": "generate",
                "run_id": "run-1",
                "stream_mode": "messages",
            }
        },
    }


@pytest.mark.asyncio
async def test_agent_stream_service_maps_langgraph_custom_events() -> None:
    provider = InMemoryAgentStreamProvider()
    service = AgentStreamService(provider)

    await service.publish_langgraph_part(
        "task-123",
        {"type": "custom", "data": {"status": "retrieving"}},
    )
    await service.publish_langgraph_part(
        "task-123",
        {
            "type": "custom",
            "data": {
                "event_type": "error",
                "message": "agent failed",
                "code": "agent_error",
            },
        },
    )

    records = [
        record async for record in service.iter_task_events("task-123", after_id="0-0")
    ]

    assert [record.event.event_type for record in records] == [
        AgentStreamEventType.PROGRESS,
        AgentStreamEventType.ERROR,
    ]
    assert records[0].event.data == {
        "metadata": {"langgraph": {"stream_mode": "custom"}},
        "status": "retrieving",
    }
    assert records[1].event.data == {
        "code": "agent_error",
        "message": "agent failed",
        "metadata": {"langgraph": {"stream_mode": "custom"}},
    }


@pytest.mark.asyncio
async def test_agent_stream_service_maps_langgraph_updates_without_state_leak() -> None:
    provider = InMemoryAgentStreamProvider()
    service = AgentStreamService(provider)

    await service.publish_langgraph_part(
        "task-123",
        {
            "type": "updates",
            "data": {"load_context": {"secret_state": "do-not-stream"}},
        },
    )

    records = [
        record async for record in service.iter_task_events("task-123", after_id="0-0")
    ]

    assert records[0].event.event_type == AgentStreamEventType.PROGRESS
    assert records[0].event.data == {
        "metadata": {
            "langgraph": {
                "nodes": ["load_context"],
                "stream_mode": "updates",
            }
        },
        "status": "graph_update",
    }
