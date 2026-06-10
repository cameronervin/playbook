"""Factory helpers for the agent streaming provider."""

from __future__ import annotations

from functools import lru_cache

from app.core.config import settings
from app.infrastructure.streaming.providers import (
    BaseAgentStreamProvider,
    ValkeyAgentStreamProvider,
)


@lru_cache
def get_agent_stream_provider() -> BaseAgentStreamProvider:
    """Return the configured agent stream provider singleton."""
    return ValkeyAgentStreamProvider(redis_url=settings.AGENT_STREAM_VALKEY_URL)


async def cleanup_agent_stream_provider() -> None:
    """Close and clear the cached provider if it has been initialized."""
    if get_agent_stream_provider.cache_info().currsize == 0:
        return
    provider = get_agent_stream_provider()
    await provider.close()
    clear_agent_stream_provider_cache()


def clear_agent_stream_provider_cache() -> None:
    """Clear the provider cache for tests."""
    get_agent_stream_provider.cache_clear()
