"""LLM provider factory.

Factory pattern for creating LLM providers based on LLM_PROVIDER_MODE.

Modes:
    - gateway: route all requests through a LiteLLM (OpenAI-compatible) gateway.
    - direct:  per-use-case provider configuration (Anthropic-first).

Pattern: StrEnum mode + @lru_cache factory + FastAPI dependency + clear_all_caches.
"""

from enum import StrEnum
from functools import lru_cache

import structlog

from app.core.config import settings
from app.infrastructure.llm.providers.base import BaseLLMProvider

logger = structlog.get_logger()


class LLMProviderMode(StrEnum):
    """Available LLM provider modes."""

    GATEWAY = "gateway"  # Route all operations through the LiteLLM gateway
    DIRECT = "direct"    # Per-use-case provider configuration


PROVIDER_MODE_DESCRIPTIONS = {
    LLMProviderMode.GATEWAY: "LiteLLM gateway — unified API access to multiple providers",
    LLMProviderMode.DIRECT: "Per-use-case provider selection with direct SDK access",
}


@lru_cache
def get_llm_provider(mode: LLMProviderMode | None = None) -> BaseLLMProvider:
    """Get the configured LLM provider (cached singleton).

    Args:
        mode: Specific provider mode, or None to read from config.

    Raises:
        ValueError: If the mode is invalid.
    """
    mode = mode or LLMProviderMode(settings.LLM_PROVIDER_MODE)

    logger.info("Initializing LLM provider", mode=mode.value)

    if mode == LLMProviderMode.GATEWAY:
        from app.infrastructure.llm.providers.gateway import GatewayLLMProvider

        return GatewayLLMProvider()

    if mode == LLMProviderMode.DIRECT:
        from app.infrastructure.llm.providers.direct import DirectLLMProvider

        return DirectLLMProvider()

    raise ValueError(f"Unknown LLM provider mode: {mode}")


def get_llm_provider_dependency(mode: LLMProviderMode | None = None) -> BaseLLMProvider:
    """FastAPI dependency for the LLM provider. Use with Depends()."""
    return get_llm_provider(mode)


def clear_all_caches() -> None:
    """Clear the factory cache and all provider-specific model caches."""
    get_llm_provider.cache_clear()

    from app.infrastructure.llm.providers.direct import clear_caches as clear_direct
    from app.infrastructure.llm.providers.gateway import clear_caches as clear_gateway

    clear_gateway()
    clear_direct()
