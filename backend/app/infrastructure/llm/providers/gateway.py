"""LiteLLM provider implementation."""

from functools import lru_cache

from langchain_core.language_models import BaseChatModel
from langchain_openai import ChatOpenAI

from app.core.config import Settings
from app.infrastructure.llm.providers.base import BaseLLMProvider

_ERR_LITELLM_KEY_REQUIRED = "LITELLM_API_KEY must be set when using LiteLLM mode"


class LiteLLMProvider(BaseLLMProvider):
    """LLM provider that routes requests through a LiteLLM proxy."""

    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    def get_chat_model(self) -> BaseChatModel:
        """Get the configured chat model via LiteLLM."""
        return _get_litellm_chat_model(
            model=self.settings.LLM_CHAT_MODEL,
            base_url=self.settings.LITELLM_BASE_URL,
            api_key=self.settings.LITELLM_API_KEY,
            temperature=self.settings.LLM_TEMPERATURE,
            max_tokens=self.settings.LLM_MAX_TOKENS,
            timeout=self.settings.LLM_TIMEOUT,
        )

    @property
    def provider_name(self) -> str:
        return "litellm"


# =============================================================================
# Cached model factories
# =============================================================================


@lru_cache
def _get_litellm_chat_model(
    *,
    model: str,
    base_url: str,
    api_key: str,
    temperature: float,
    max_tokens: int,
    timeout: int,
) -> BaseChatModel:
    if not api_key:
        raise ValueError(_ERR_LITELLM_KEY_REQUIRED)

    return ChatOpenAI(
        model=model,
        base_url=base_url,
        api_key=api_key,
        temperature=temperature,
        max_tokens=max_tokens,
        timeout=timeout,
    )


def clear_caches() -> None:
    """Clear all cached model instances (useful for tests / config changes)."""
    _get_litellm_chat_model.cache_clear()
