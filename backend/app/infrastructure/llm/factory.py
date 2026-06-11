"""LLM provider factory."""

from enum import StrEnum
from typing import Annotated

import structlog
from fastapi import Depends

from app.core.config import Settings, get_request_settings, get_settings
from app.infrastructure.llm.providers.base import BaseLLMProvider

logger = structlog.get_logger()


class LLMProviderMode(StrEnum):
    """Available LLM provider modes."""

    DIRECT = "direct"
    LITELLM = "litellm"


PROVIDER_MODE_DESCRIPTIONS = {
    LLMProviderMode.DIRECT: "Direct provider SDK access",
    LLMProviderMode.LITELLM: "LiteLLM proxy — unified API access to multiple providers",
}


_provider_cache: dict[tuple[LLMProviderMode, str], BaseLLMProvider] = {}


def _build_llm_provider(
    mode: LLMProviderMode,
    app_settings: Settings,
) -> BaseLLMProvider:
    logger.info("Initializing LLM provider", mode=mode.value)

    if mode == LLMProviderMode.LITELLM:
        from app.infrastructure.llm.providers.gateway import LiteLLMProvider

        return LiteLLMProvider(app_settings)

    if mode == LLMProviderMode.DIRECT:
        from app.infrastructure.llm.providers.direct import DirectLLMProvider

        return DirectLLMProvider(app_settings)

    raise ValueError(f"Unknown LLM provider mode: {mode}")


def get_llm_provider(
    mode: LLMProviderMode | None = None,
    app_settings: Settings | None = None,
) -> BaseLLMProvider:
    """Get the configured LLM provider (cached singleton).

    Args:
        mode: Specific provider mode, or None to read from config.

    Raises:
        ValueError: If the mode is invalid.
    """
    settings = app_settings or get_settings()
    resolved_mode = mode or LLMProviderMode(settings.LLM_PROVIDER_MODE)
    cache_key = (resolved_mode, settings.model_dump_json())
    if cache_key not in _provider_cache:
        _provider_cache[cache_key] = _build_llm_provider(resolved_mode, settings)
    return _provider_cache[cache_key]


def get_llm_provider_dependency(
    app_settings: Annotated[Settings, Depends(get_request_settings)],
) -> BaseLLMProvider:
    """FastAPI dependency for the LLM provider. Use with Depends()."""
    return get_llm_provider(app_settings=app_settings)


def clear_all_caches() -> None:
    """Clear the factory cache and all provider-specific model caches."""
    _provider_cache.clear()

    from app.infrastructure.llm.providers.direct import clear_caches as clear_direct
    from app.infrastructure.llm.providers.gateway import clear_caches as clear_litellm

    clear_litellm()
    clear_direct()
