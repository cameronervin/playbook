"""Knowledgebase provider factory.

Mirrors the LLM provider factory pattern. The factory is @lru_cache so a single
provider instance is shared for the application lifetime. Call
clear_kb_provider_cache() in tests to reset state.

Modes: LOCAL (httpx-backed KB service) and MOCK (offline fixtures).
"""
from __future__ import annotations

from enum import StrEnum
from functools import lru_cache
from typing import Protocol

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
    from app.core.config import settings as default_settings

    s = cfg if cfg is not None else default_settings
    # Validate the mode is known; raises ValueError on an unknown value.
    KBProviderMode(s.KB_PROVIDER_MODE)
    return s.KB_ENABLED


@lru_cache(maxsize=1)
def get_kb_provider(mode: KBProviderMode | None = None) -> BaseKnowledgebaseProvider:
    """Return the singleton knowledgebase provider for the given mode.

    The instance is cached via @lru_cache. Lazy imports keep startup fast and
    avoid importing httpx when using the mock provider.

    Args:
        mode: KBProviderMode value. Defaults to settings.KB_PROVIDER_MODE.

    Raises:
        ValueError: If an unknown mode is provided.
    """
    from app.core.config import settings

    resolved_mode = mode or KBProviderMode(settings.KB_PROVIDER_MODE)

    if resolved_mode == KBProviderMode.LOCAL:
        from app.infrastructure.knowledgebase.providers.local_kb import LocalKBProvider

        return LocalKBProvider()

    if resolved_mode == KBProviderMode.MOCK:
        from app.infrastructure.knowledgebase.providers.mock import MockProvider

        return MockProvider()

    raise ValueError(f"Unknown KB provider mode: {resolved_mode!r}")


def get_kb_provider_dependency() -> BaseKnowledgebaseProvider:
    """FastAPI dependency that returns the cached KB provider. Use with Depends()."""
    return get_kb_provider()


def clear_kb_provider_cache() -> None:
    """Clear the @lru_cache so a fresh provider is created on next call.

    Call this in test teardown to prevent state leakage between tests that use
    different provider modes.
    """
    get_kb_provider.cache_clear()
