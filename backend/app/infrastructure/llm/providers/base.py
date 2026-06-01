"""Base LLM provider interface.

Defines the abstract base class for all LLM providers, giving a consistent
surface for chat and (high-capability) research model access across provider
implementations.

Two provider modes are supported:
    - Gateway: routes all requests through a LiteLLM (OpenAI-compatible) gateway.
    - Direct:  uses per-use-case provider configuration (Anthropic-first).
"""

from abc import ABC, abstractmethod

from langchain_core.language_models import BaseChatModel


class BaseLLMProvider(ABC):
    """Abstract base class for LLM providers.

    Methods:
        get_chat_model: returns a LangChain chat model for conversation.
        get_research_model: returns a high-capability ("advanced" tier) model
            for complex reasoning — currently a NotImplementedError stub.
        provider_name: returns the provider identifier for logging.
        health_check: validates provider connectivity.

    NOTE: domain-specific model accessors (e.g. vision/multimodal, embeddings,
    image generation) belong here too — add them as new abstract methods when a
    consumer needs them.
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

    @abstractmethod
    def get_research_model(self) -> BaseChatModel:
        """Get the high-capability research / advanced-tier model.

        Reserved for workflows that require the most capable model. Currently
        a placeholder — concrete providers raise NotImplementedError until a
        consumer is wired up.

        Returns:
            A LangChain BaseChatModel configured for advanced reasoning.

        Raises:
            NotImplementedError: Stub — implementation lands in a follow-up task.
        """
        ...

    @property
    @abstractmethod
    def provider_name(self) -> str:
        """Provider identifier for logging and debugging (e.g. 'direct', 'gateway')."""
        ...

    def health_check(self) -> bool:
        """Check whether the provider is healthy and accessible.

        Default implementation returns True. Subclasses can override to
        implement real connectivity checks.
        """
        return True
