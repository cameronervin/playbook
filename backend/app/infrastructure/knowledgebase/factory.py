"""Knowledgebase provider factory.

Mirrors the LLM provider factory pattern. The factory is @lru_cache so a single
provider instance is shared for the application lifetime. Call
clear_kb_provider_cache() in tests to reset state.

Modes: LOCAL (httpx-backed KB service) and MOCK (offline fixtures).
"""
from __future__ import annotations

from enum import StrEnum
from typing import Annotated, Protocol

from fastapi import Depends

from app.core.config import Settings, get_request_settings, get_settings
from app.infrastructure.knowledgebase.providers.base import BaseKnowledgebaseProvider


class _KbSettingsView(Protocol):
    """Subset of Settings used by ``is_kb_feature_enabled``."""

    KB_PROVIDER_MODE: str
    KB_ENABLED: bool


class KBProviderMode(StrEnum):
    LOCAL = "local"
    MOCK = "mock"


def is_kb_feature_enabled(cfg: _KbSettingsView | None = None) -> bool:
    """Whether the app should attach KB tools and initialize a KB provider.

    Both local and mock modes are gated only by the ``KB_ENABLED`` kill switch.

    Args:
        cfg: Optional settings object (or a test double). Defaults to
            ``app.core.config.settings``.
    """
    s = cfg if cfg is not None else get_settings()
    # Validate the mode is known; raises ValueError on an unknown value.
    KBProviderMode(s.KB_PROVIDER_MODE)
    return s.KB_ENABLED


_provider_cache: dict[tuple[KBProviderMode, str], BaseKnowledgebaseProvider] = {}


def get_kb_provider(
    mode: KBProviderMode | None = None,
    app_settings: Settings | None = None,
) -> BaseKnowledgebaseProvider:
    """Return the singleton knowledgebase provider for the given mode.

    The instance is cached via @lru_cache. Lazy imports keep startup fast and
    avoid importing httpx when using the mock provider.

    Args:
        mode: KBProviderMode value. Defaults to settings.KB_PROVIDER_MODE.

    Raises:
        ValueError: If an unknown mode is provided.
    """
    settings = app_settings or get_settings()
    resolved_mode = mode or KBProviderMode(settings.KB_PROVIDER_MODE)
    cache_key = (resolved_mode, settings.model_dump_json())
    if cache_key in _provider_cache:
        return _provider_cache[cache_key]

    if resolved_mode == KBProviderMode.LOCAL:
        from app.infrastructure.knowledgebase.providers.local_kb import LocalKBProvider

        _provider_cache[cache_key] = LocalKBProvider(settings)
        return _provider_cache[cache_key]

    if resolved_mode == KBProviderMode.MOCK:
        from app.infrastructure.knowledgebase.providers.mock import MockProvider

        _provider_cache[cache_key] = MockProvider(settings)
        return _provider_cache[cache_key]

    raise ValueError(f"Unknown KB provider mode: {resolved_mode!r}")


def get_kb_provider_dependency(
    app_settings: Annotated[Settings, Depends(get_request_settings)],
) -> BaseKnowledgebaseProvider:
    """FastAPI dependency that returns the cached KB provider. Use with Depends()."""
    return get_kb_provider(app_settings=app_settings)


def clear_kb_provider_cache() -> None:
    """Clear the @lru_cache so a fresh provider is created on next call.

    Call this in test teardown to prevent state leakage between tests that use
    different provider modes.
    """
    _provider_cache.clear()
