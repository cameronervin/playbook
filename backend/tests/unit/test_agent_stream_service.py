"""Unit tests for the agent stream service scaffold."""

from __future__ import annotations

import pytest

from app.infrastructure.streaming import (
    AgentStreamEventType,
    InMemoryAgentStreamProvider,
)
from app.services.agent_stream_service import AgentStreamService


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
