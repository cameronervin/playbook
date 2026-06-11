"""Direct LLM provider with one configured chat model."""

from functools import lru_cache

from langchain_core.language_models import BaseChatModel

from app.core.config import Settings
from app.infrastructure.llm.providers.base import BaseLLMProvider


class DirectLLMProvider(BaseLLMProvider):
    """Direct API provider with per-use-case provider selection.

    Uses @lru_cache on model creation so each model is a singleton.
    """

    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    def get_chat_model(self) -> BaseChatModel:
        """Get the chat model based on LLM_DIRECT_PROVIDER / LLM_CHAT_MODEL."""
        return _get_chat_model_cached(
            provider=self.settings.LLM_DIRECT_PROVIDER,
            model=self.settings.LLM_CHAT_MODEL,
            temperature=self.settings.LLM_TEMPERATURE,
            max_tokens=self.settings.LLM_MAX_TOKENS,
            timeout=self.settings.LLM_TIMEOUT,
            anthropic_api_key=self.settings.ANTHROPIC_API_KEY,
            openai_api_key=self.settings.OPENAI_API_KEY,
            gemini_api_key=self.settings.GEMINI_API_KEY,
        )

    @property
    def provider_name(self) -> str:
        return "direct"


# =============================================================================
# Cached model factories
# =============================================================================


@lru_cache
def _get_chat_model_cached(
    *,
    provider: str,
    model: str,
    temperature: float,
    max_tokens: int,
    timeout: int,
    anthropic_api_key: str | None,
    openai_api_key: str | None,
    gemini_api_key: str | None,
) -> BaseChatModel:
    """Create a LangChain chat model for the specified provider.

    Args:
        provider: 'anthropic' (default), 'openai', or 'google'.
        model: Model name/identifier.
        temperature: Sampling temperature.

    Raises:
        ValueError: If the API key is missing or the provider is unknown.
    """
    if provider == "anthropic":
        _validate_api_key(anthropic_api_key, "ANTHROPIC_API_KEY", "anthropic")
        from langchain_anthropic import ChatAnthropic

        return ChatAnthropic(
            model=model,
            api_key=anthropic_api_key,
            temperature=temperature,
            max_tokens=max_tokens,
            timeout=float(timeout),
        )

    if provider == "openai":
        # Alternative provider — requires `langchain-openai`.
        _validate_api_key(openai_api_key, "OPENAI_API_KEY", "openai")
        from langchain_openai import ChatOpenAI

        return ChatOpenAI(
            model=model,
            api_key=openai_api_key,
            temperature=temperature,
            max_tokens=max_tokens,
            timeout=timeout,
        )

    if provider == "google":
        # Alternative provider — requires `langchain-google-genai`.
        _validate_api_key(gemini_api_key, "GEMINI_API_KEY", "google")
        from langchain_google_genai import ChatGoogleGenerativeAI

        return ChatGoogleGenerativeAI(
            model=model,
            google_api_key=gemini_api_key,
            temperature=temperature,
            max_output_tokens=max_tokens,
            timeout=timeout,
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
