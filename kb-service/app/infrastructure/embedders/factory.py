"""Canonical embed provider factory.

Two construction paths:
  * ``get_embed_provider`` — ``@lru_cache`` process-wide singleton. Safe for
    sync callers (the API path) where one shared httpx connection pool is fine.
  * ``build_fresh_embed_provider`` — NON-cached. Worker threads MUST use this:
    the underlying httpx client binds to the creating thread's event loop, so a
    cached singleton shared across threads triggers "Event loop is closed"
    races. Each worker thread builds its own loop-bound client instead.

``OpenAI`` is imported lazily inside ``build_fresh_embed_provider`` so this
module compiles without ``openai`` installed.
"""
from __future__ import annotations

from functools import lru_cache

import structlog

from app.core.config import settings
from app.infrastructure.embedders.base import BaseEmbedProvider, EmbedProviderMode
from app.infrastructure.embedders.direct import DirectEmbedProvider
from app.infrastructure.embedders.gateway import GatewayEmbedProvider
from app.infrastructure.llm.builder import (
    clear_client_caches,
    get_direct_embed_client,
    get_gateway_embed_client,
)

logger = structlog.get_logger(__name__)


@lru_cache
def get_embed_provider(mode: EmbedProviderMode | None = None) -> BaseEmbedProvider:
    """Process-wide singleton — safe for sync callers (API path).

    Worker threads MUST NOT use this: the underlying httpx client binds to the
    creating thread's event loop. Use ``build_fresh_embed_provider()`` instead
    so each worker thread gets its own loop-bound client.
    """
    mode = mode or EmbedProviderMode(settings.KB_LLM_PROVIDER_MODE)

    logger.info("kb_embed_provider_init", mode=mode.value)

    if mode == EmbedProviderMode.GATEWAY:
        return GatewayEmbedProvider(client=get_gateway_embed_client())

    if mode == EmbedProviderMode.DIRECT:
        return DirectEmbedProvider(client=get_direct_embed_client())

    raise ValueError(f"Unknown embed provider mode: {mode!r}")


def build_fresh_embed_provider(mode: EmbedProviderMode | None = None) -> BaseEmbedProvider:
    """Build a NON-CACHED embed provider — used by per-thread worker state.

    Uses the sync ``OpenAI`` client (not ``AsyncOpenAI``): the async client +
    ``asyncio.run()`` per-task pattern caused intermittent "Event loop is
    closed" failures during httpx connection-pool cleanup (openai-python#1254).
    The sync client has no such race — its httpx connection pool is shared
    safely across all calls on the same thread, eliminating both the bug class
    AND the per-task TLS handshake overhead.
    """
    from openai import OpenAI

    mode = mode or EmbedProviderMode(settings.KB_LLM_PROVIDER_MODE)
    if mode == EmbedProviderMode.GATEWAY:
        if not settings.LLM_GATEWAY_BASE_URL or not settings.LLM_GATEWAY_API_KEY:
            raise ValueError("Gateway mode requires LLM_GATEWAY_BASE_URL and LLM_GATEWAY_API_KEY")
        client = OpenAI(
            base_url=settings.LLM_GATEWAY_BASE_URL,
            api_key=settings.LLM_GATEWAY_API_KEY,
            timeout=settings.KB_EMBED_REQUEST_TIMEOUT_SECONDS,
            max_retries=0,
        )
        return GatewayEmbedProvider(client=client)
    if mode == EmbedProviderMode.DIRECT:
        if not settings.OPENAI_API_KEY:
            raise ValueError("Direct mode requires OPENAI_API_KEY")
        client = OpenAI(
            api_key=settings.OPENAI_API_KEY,
            timeout=settings.KB_EMBED_REQUEST_TIMEOUT_SECONDS,
            max_retries=0,
        )
        return DirectEmbedProvider(client=client)
    raise ValueError(f"Unknown embed provider mode: {mode!r}")


def clear_all_caches() -> None:
    get_embed_provider.cache_clear()
    clear_client_caches()


__all__ = [
    "EmbedProviderMode",
    "get_embed_provider",
    "build_fresh_embed_provider",
    "clear_all_caches",
]
