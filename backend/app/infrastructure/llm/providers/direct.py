"""Direct LLM provider with one configured chat model."""

from functools import lru_cache

from langchain_core.language_models import BaseChatModel

from app.core.config import settings
from app.infrastructure.llm.providers.base import BaseLLMProvider


class DirectLLMProvider(BaseLLMProvider):
    """Direct API provider with per-use-case provider selection.

    Uses @lru_cache on model creation so each model is a singleton.
    """

    def get_chat_model(self) -> BaseChatModel:
        """Get the chat model based on LLM_DIRECT_PROVIDER / LLM_CHAT_MODEL."""
        return _get_chat_model_cached()

    @property
    def provider_name(self) -> str:
        return "direct"


# =============================================================================
# Cached model factories
# =============================================================================


@lru_cache
def _get_chat_model_cached() -> BaseChatModel:
    return _create_chat_model(
        provider=settings.LLM_DIRECT_PROVIDER,
        model=settings.LLM_CHAT_MODEL,
        temperature=settings.LLM_TEMPERATURE,
    )


def _create_chat_model(provider: str, model: str, temperature: float) -> BaseChatModel:
    """Create a LangChain chat model for the specified provider.

    Args:
        provider: 'anthropic' (default), 'openai', or 'google'.
        model: Model name/identifier.
        temperature: Sampling temperature.

    Raises:
        ValueError: If the API key is missing or the provider is unknown.
    """
    if provider == "anthropic":
        _validate_api_key(settings.ANTHROPIC_API_KEY, "ANTHROPIC_API_KEY", "anthropic")
        from langchain_anthropic import ChatAnthropic

        return ChatAnthropic(
            model=model,
            api_key=settings.ANTHROPIC_API_KEY,
            temperature=temperature,
            max_tokens=settings.LLM_MAX_TOKENS,
            timeout=float(settings.LLM_TIMEOUT),
        )

    if provider == "openai":
        # Alternative provider — requires `langchain-openai`.
        _validate_api_key(settings.OPENAI_API_KEY, "OPENAI_API_KEY", "openai")
        from langchain_openai import ChatOpenAI

        return ChatOpenAI(
            model=model,
            api_key=settings.OPENAI_API_KEY,
            temperature=temperature,
            max_tokens=settings.LLM_MAX_TOKENS,
            timeout=settings.LLM_TIMEOUT,
        )

    if provider == "google":
        # Alternative provider — requires `langchain-google-genai`.
        _validate_api_key(settings.GEMINI_API_KEY, "GEMINI_API_KEY", "google")
        from langchain_google_genai import ChatGoogleGenerativeAI

        return ChatGoogleGenerativeAI(
            model=model,
            google_api_key=settings.GEMINI_API_KEY,
            temperature=temperature,
            max_output_tokens=settings.LLM_MAX_TOKENS,
            timeout=settings.LLM_TIMEOUT,
        )

    raise ValueError(f"Unknown provider: {provider}. Valid options: anthropic, openai, google")


def _validate_api_key(key: str | None, key_name: str, provider: str) -> None:
    """Validate that an API key is set, raising a clear error if not."""
    if not key:
        raise ValueError(
            f"{key_name} is required when using the {provider} provider. "
            f"Set {key_name} in your environment or .env file."
        )


def clear_caches() -> None:
    """Clear all cached model instances (useful for tests / config changes)."""
    _get_chat_model_cached.cache_clear()
