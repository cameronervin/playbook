"""Base LLM provider interface."""

from abc import ABC, abstractmethod

from langchain_core.language_models import BaseChatModel


class BaseLLMProvider(ABC):
    """Abstract base class for LLM providers.

    Add domain-specific accessors only when a concrete consumer needs them.
    """

    @abstractmethod
    def get_chat_model(self) -> BaseChatModel:
        """Get the chat model for conversation.

        Returns:
            A LangChain BaseChatModel configured for chat operations.

        Raises:
            ValueError: If the provider is not configured correctly.
        """
        ...

    @property
    @abstractmethod
    def provider_name(self) -> str:
        """Provider identifier for logging and debugging."""
        ...

    def health_check(self) -> bool:
        """Check whether the provider is healthy and accessible.

        Default implementation returns True. Subclasses can override to
        implement real connectivity checks.
        """
        return True
