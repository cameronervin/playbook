"""Factory helpers for the agent streaming provider."""

from __future__ import annotations

from typing import Annotated

from fastapi import Depends

from app.core.config import Settings, get_request_settings, get_settings
from app.infrastructure.streaming.providers import (
    BaseAgentStreamProvider,
    ValkeyAgentStreamProvider,
)

_provider_cache: dict[str, BaseAgentStreamProvider] = {}


def get_agent_stream_provider(
    app_settings: Settings | None = None,
) -> BaseAgentStreamProvider:
    """Return the configured agent stream provider singleton."""
    settings = app_settings or get_settings()
    cache_key = settings.AGENT_STREAM_VALKEY_URL
    if cache_key not in _provider_cache:
        _provider_cache[cache_key] = ValkeyAgentStreamProvider(
            redis_url=settings.AGENT_STREAM_VALKEY_URL
        )
    return _provider_cache[cache_key]


def get_agent_stream_provider_dependency(
    app_settings: Annotated[Settings, Depends(get_request_settings)],
) -> BaseAgentStreamProvider:
    """FastAPI dependency for the agent stream provider."""
    return get_agent_stream_provider(app_settings)


async def cleanup_agent_stream_provider() -> None:
    """Close and clear the cached provider if it has been initialized."""
    for provider in _provider_cache.values():
        await provider.close()
    clear_agent_stream_provider_cache()


def clear_agent_stream_provider_cache() -> None:
    """Clear the provider cache for tests."""
    _provider_cache.clear()
