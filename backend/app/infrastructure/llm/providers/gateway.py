"""Gateway LLM provider implementation.

Routes all LLM requests through a LiteLLM gateway (settings.LLM_GATEWAY_BASE_URL)
using the OpenAI-compatible ChatOpenAI client. This is the recommended mode for
production: unified API access, centralized rate limiting, cost tracking, and
observability. Model aliases (e.g. Claude ids) are registered on the gateway.
"""

from functools import lru_cache

from langchain_core.language_models import BaseChatModel
from langchain_openai import ChatOpenAI

from app.core.config import settings
from app.infrastructure.llm.providers.base import BaseLLMProvider

_ERR_GATEWAY_KEY_REQUIRED = "LLM_GATEWAY_API_KEY must be set when using gateway mode"


class GatewayLLMProvider(BaseLLMProvider):
    """LLM provider that routes requests through a LiteLLM gateway."""

    def get_chat_model(self) -> BaseChatModel:
        """Get the chat model via the gateway."""
        return _get_gateway_chat_model()

    def get_research_model(self) -> BaseChatModel:
        """Get the advanced/research model via the gateway (stub)."""
        return _get_gateway_research_model()

    @property
    def provider_name(self) -> str:
        return "gateway"


# =============================================================================
# Cached model factories (module-level for singleton behavior)
# =============================================================================


@lru_cache
def _get_gateway_chat_model() -> BaseChatModel:
    if not settings.LLM_GATEWAY_API_KEY:
        raise ValueError(_ERR_GATEWAY_KEY_REQUIRED)

    return ChatOpenAI(
        model=settings.LLM_CHAT_MODEL,
        base_url=settings.LLM_GATEWAY_BASE_URL,
        api_key=settings.LLM_GATEWAY_API_KEY,
        temperature=settings.LLM_TEMPERATURE,
        max_tokens=settings.LLM_MAX_TOKENS,
        timeout=settings.LLM_TIMEOUT,
    )


@lru_cache
def _get_gateway_research_model() -> BaseChatModel:
    """Stub — implementation pending.

    Will instantiate ChatOpenAI with settings.LLM_RESEARCH_MODEL once a
    research/advanced-tier consumer is wired up.
    """
    raise NotImplementedError(
        "Gateway research model is a stub — implementation pending. "
        f"Configured model: {settings.LLM_RESEARCH_MODEL}"
    )


def clear_caches() -> None:
    """Clear all cached model instances (useful for tests / config changes)."""
    _get_gateway_chat_model.cache_clear()
    _get_gateway_research_model.cache_clear()
