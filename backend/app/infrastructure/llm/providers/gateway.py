"""LiteLLM provider implementation."""

from functools import lru_cache

from langchain_core.language_models import BaseChatModel
from langchain_openai import ChatOpenAI

from app.core.config import settings
from app.infrastructure.llm.providers.base import BaseLLMProvider

_ERR_LITELLM_KEY_REQUIRED = "LITELLM_API_KEY must be set when using LiteLLM mode"


class LiteLLMProvider(BaseLLMProvider):
    """LLM provider that routes requests through a LiteLLM proxy."""

    def get_chat_model(self) -> BaseChatModel:
        """Get the configured chat model via LiteLLM."""
        return _get_litellm_chat_model()

    @property
    def provider_name(self) -> str:
        return "litellm"


# =============================================================================
# Cached model factories
# =============================================================================


@lru_cache
def _get_litellm_chat_model() -> BaseChatModel:
    if not settings.LITELLM_API_KEY:
        raise ValueError(_ERR_LITELLM_KEY_REQUIRED)

    return ChatOpenAI(
        model=settings.LLM_CHAT_MODEL,
        base_url=settings.LITELLM_BASE_URL,
        api_key=settings.LITELLM_API_KEY,
        temperature=settings.LLM_TEMPERATURE,
        max_tokens=settings.LLM_MAX_TOKENS,
        timeout=settings.LLM_TIMEOUT,
    )


def clear_caches() -> None:
    """Clear all cached model instances (useful for tests / config changes)."""
    _get_litellm_chat_model.cache_clear()
