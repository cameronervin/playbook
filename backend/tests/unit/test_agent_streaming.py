"""Unit tests for the agent streaming infrastructure scaffold."""

from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import AsyncMock

import pytest

from app.infrastructure.streaming import (
    AgentStreamEvent,
    AgentStreamEventType,
    InMemoryAgentStreamProvider,
    ValkeyAgentStreamProvider,
)


def test_agent_stream_event_serializes_round_trip() -> None:
    event = AgentStreamEvent(
        task_id="task-123",
        event_type=AgentStreamEventType.CHUNK,
        data={"content": "hello", "index": 1},
        created_at=datetime(2026, 6, 10, 12, 30, tzinfo=UTC),
    )

    fields = event.to_stream_fields()
    restored = AgentStreamEvent.from_stream_fields(fields)

    assert fields["event_type"] == "chunk"
    assert restored == event


def test_agent_stream_event_rejects_unknown_event_type() -> None:
    with pytest.raises(ValueError):
        AgentStreamEvent.from_stream_fields(
            {
                "task_id": "task-123",
                "event_type": "unknown",
                "data": "{}",
                "created_at": "2026-06-10T12:30:00+00:00",
            }
        )


@pytest.mark.asyncio
async def test_in_memory_provider_preserves_order_and_stops_at_terminal_event() -> None:
    provider = InMemoryAgentStreamProvider()

    first_id = await provider.publish_event(
        AgentStreamEvent(
            task_id="task-123",
            event_type=AgentStreamEventType.PROGRESS,
            data={"status": "retrieving"},
        )
    )
    second_id = await provider.publish_event(
        AgentStreamEvent(
            task_id="task-123",
            event_type=AgentStreamEventType.COMPLETE,
            data={"message_id": "assistant-123"},
        )
    )

    records = [
        record async for record in provider.iter_events("task-123", after_id="0-0")
    ]

    assert [first_id, second_id] == ["1-0", "2-0"]
    assert [record.event.event_type for record in records] == [
        AgentStreamEventType.PROGRESS,
        AgentStreamEventType.COMPLETE,
    ]


@pytest.mark.asyncio
async def test_in_memory_provider_respects_after_id() -> None:
    provider = InMemoryAgentStreamProvider()
    await provider.publish_event(
        AgentStreamEvent(
            task_id="task-123",
            event_type=AgentStreamEventType.CHUNK,
            data={"content": "first"},
        )
    )
    await provider.publish_event(
        AgentStreamEvent(
            task_id="task-123",
            event_type=AgentStreamEventType.COMPLETE,
            data={},
        )
    )

    records = [
        record async for record in provider.iter_events("task-123", after_id="1-0")
    ]

    assert [record.stream_id for record in records] == ["2-0"]


@pytest.mark.asyncio
async def test_valkey_provider_publishes_to_task_stream_and_notification_channel() -> None:
    redis_client = AsyncMock()
    redis_client.xadd.return_value = "1749560000000-0"
    provider = ValkeyAgentStreamProvider(
        redis_url="redis://localhost:6379/2",
        redis_client=redis_client,
    )

    stream_id = await provider.publish_event(
        AgentStreamEvent(
            task_id="task-123",
            event_type=AgentStreamEventType.CHUNK,
            data={"content": "hello"},
        )
    )

    assert stream_id == "1749560000000-0"
    redis_client.xadd.assert_awaited_once()
    stream_key, fields = redis_client.xadd.await_args.args[:2]
    assert stream_key == "agent-stream:task-123:events"
    assert fields["event_type"] == "chunk"
    redis_client.publish.assert_awaited_once_with(
        "agent-stream:task-123:notify",
        "1749560000000-0",
    )


@pytest.mark.asyncio
async def test_valkey_provider_reads_stream_records_from_xread() -> None:
    redis_client = AsyncMock()
    redis_client.xread.return_value = [
        (
            "agent-stream:task-123:events",
            [
                (
                    "1749560000000-0",
                    {
                        "task_id": "task-123",
                        "event_type": "complete",
                        "data": "{}",
                        "created_at": "2026-06-10T12:30:00+00:00",
                    },
                )
            ],
        )
    ]
    provider = ValkeyAgentStreamProvider(
        redis_url="redis://localhost:6379/2",
        redis_client=redis_client,
        block_ms=1,
    )

    records = [
        record async for record in provider.iter_events("task-123", after_id="0-0")
    ]

    assert records[0].stream_id == "1749560000000-0"
    assert records[0].event.event_type == AgentStreamEventType.COMPLETE
    redis_client.xread.assert_awaited_once_with(
        streams={"agent-stream:task-123:events": "0-0"},
        count=100,
        block=1,
    )
