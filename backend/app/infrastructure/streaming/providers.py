"""Agent stream provider interfaces and implementations."""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import AsyncIterator, Mapping, Sequence
from typing import Any, Protocol

from app.infrastructure.streaming.events import (
    AgentStreamEvent,
    AgentStreamRecord,
)

DEFAULT_STREAM_NAMESPACE = "agent-stream"
DEFAULT_READ_COUNT = 100
DEFAULT_BLOCK_MS = 5000


class BaseAgentStreamProvider(ABC):
    """Storage and notification contract for task-scoped agent stream events."""

    @abstractmethod
    async def publish_event(self, event: AgentStreamEvent) -> str:
        """Persist an event and notify active consumers."""

    @abstractmethod
    def iter_events(
        self,
        task_id: str,
        *,
        after_id: str = "0-0",
    ) -> AsyncIterator[AgentStreamRecord]:
        """Yield task events after the supplied stream ID."""

    @abstractmethod
    async def close(self) -> None:
        """Release provider resources."""


class AsyncRedisClient(Protocol):
    """Subset of redis.asyncio used by the streaming provider."""

    async def xadd(
        self,
        name: str,
        fields: Mapping[str, str],
        *,
        maxlen: int | None = None,
        approximate: bool = True,
    ) -> str | bytes:
        """Add one record to a Redis Stream."""

    async def xread(
        self,
        *,
        streams: Mapping[str, str],
        count: int,
        block: int,
    ) -> Sequence[tuple[str | bytes, Sequence[tuple[str | bytes, dict[str, str | bytes]]]]]:
        """Read records from one or more Redis Streams."""

    async def publish(self, channel: str, message: str) -> int:
        """Publish a notification to a Redis channel."""

    def pubsub(self) -> "AsyncRedisPubSub":
        """Create a pub/sub connection context manager."""

    async def aclose(self) -> None:
        """Close the Redis client."""


class AsyncRedisPubSub(Protocol):
    """Subset of redis.asyncio PubSub used for stream wake-ups."""

    async def __aenter__(self) -> "AsyncRedisPubSub":
        """Enter the pub/sub context manager."""

    async def __aexit__(self, *args: Any) -> None:
        """Exit the pub/sub context manager."""

    async def subscribe(self, *channels: str) -> None:
        """Subscribe to one or more channels."""

    async def unsubscribe(self, *channels: str) -> None:
        """Unsubscribe from one or more channels."""

    async def get_message(
        self,
        *,
        ignore_subscribe_messages: bool,
        timeout: float | None,
    ) -> Any:
        """Wait for one pub/sub message."""


class InMemoryAgentStreamProvider(BaseAgentStreamProvider):
    """No-network provider used by unit tests and local fakes."""

    def __init__(self) -> None:
        self._records_by_task: dict[str, list[AgentStreamRecord]] = {}

    async def publish_event(self, event: AgentStreamEvent) -> str:
        """Append an event to the in-memory task stream."""
        records = self._records_by_task.setdefault(event.task_id, [])
        stream_id = f"{len(records) + 1}-0"
        records.append(AgentStreamRecord(stream_id=stream_id, event=event))
        return stream_id

    async def iter_events(
        self,
        task_id: str,
        *,
        after_id: str = "0-0",
    ) -> AsyncIterator[AgentStreamRecord]:
        """Yield stored records after *after_id* until exhausted or terminal."""
        for record in self._records_by_task.get(task_id, []):
            if _stream_id_is_after(record.stream_id, after_id):
                yield record
                if record.event.is_terminal:
                    return

    async def close(self) -> None:
        """Clear in-memory stream records."""
        self._records_by_task.clear()


class ValkeyAgentStreamProvider(BaseAgentStreamProvider):
    """Valkey/Redis Streams provider for agent response events."""

    def __init__(
        self,
        *,
        redis_url: str,
        redis_client: AsyncRedisClient | None = None,
        namespace: str = DEFAULT_STREAM_NAMESPACE,
        maxlen: int = 1000,
        read_count: int = DEFAULT_READ_COUNT,
        block_ms: int = DEFAULT_BLOCK_MS,
    ) -> None:
        self.redis_url = redis_url
        self._redis_client = redis_client
        self.namespace = namespace
        self.maxlen = maxlen
        self.read_count = read_count
        self.block_ms = block_ms

    async def publish_event(self, event: AgentStreamEvent) -> str:
        """Persist an event to Valkey Streams and notify subscribers."""
        client = self._get_client()
        stream_id = await client.xadd(
            self.stream_key(event.task_id),
            event.to_stream_fields(),
            maxlen=self.maxlen,
            approximate=True,
        )
        decoded_stream_id = _decode_stream_id(stream_id)
        await client.publish(self.channel_name(event.task_id), decoded_stream_id)
        return decoded_stream_id

    async def iter_events(
        self,
        task_id: str,
        *,
        after_id: str = "0-0",
    ) -> AsyncIterator[AgentStreamRecord]:
        """Read task stream records after *after_id* until a terminal event."""
        client = self._get_client()
        last_id = after_id
        channel_name = self.channel_name(task_id)
        async with client.pubsub() as pubsub:
            await pubsub.subscribe(channel_name)
            try:
                while True:
                    saw_records = False
                    response = await client.xread(
                        streams={self.stream_key(task_id): last_id},
                        count=self.read_count,
                        block=self.block_ms,
                    )
                    for _stream_name, entries in response:
                        for raw_stream_id, fields in entries:
                            saw_records = True
                            stream_id = _decode_stream_id(raw_stream_id)
                            event = AgentStreamEvent.from_stream_fields(fields)
                            yield AgentStreamRecord(stream_id=stream_id, event=event)
                            last_id = stream_id
                            if event.is_terminal:
                                return

                    if not saw_records:
                        await pubsub.get_message(
                            ignore_subscribe_messages=True,
                            timeout=self.block_ms / 1000,
                        )
            finally:
                await pubsub.unsubscribe(channel_name)

    def stream_key(self, task_id: str) -> str:
        """Return the Valkey stream key for a task."""
        return f"{self.namespace}:{task_id}:events"

    def channel_name(self, task_id: str) -> str:
        """Return the Valkey pub/sub wake-up channel for a task."""
        return f"{self.namespace}:{task_id}:notify"

    async def close(self) -> None:
        """Close the underlying Redis client if it has been created."""
        if self._redis_client is not None:
            await self._redis_client.aclose()
            self._redis_client = None

    def _get_client(self) -> AsyncRedisClient:
        if self._redis_client is None:
            import redis.asyncio as redis

            self._redis_client = redis.from_url(
                self.redis_url,
                decode_responses=True,
            )
        return self._redis_client


def _decode_stream_id(stream_id: str | bytes) -> str:
    if isinstance(stream_id, bytes):
        return stream_id.decode("utf-8")
    return stream_id


def _stream_id_is_after(candidate: str, after_id: str) -> bool:
    candidate_time, candidate_sequence = _parse_stream_id(candidate)
    after_time, after_sequence = _parse_stream_id(after_id)
    return (candidate_time, candidate_sequence) > (after_time, after_sequence)


def _parse_stream_id(stream_id: str) -> tuple[int, int]:
    time_part, sequence_part = stream_id.split("-", maxsplit=1)
    return int(time_part), int(sequence_part)
