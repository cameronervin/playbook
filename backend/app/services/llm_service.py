"""Application-facing LLM service.

Thin orchestration layer over the LLM provider abstraction. Keeps business
logic out of the raw provider/client code and exposes a stable surface for
routes and agents. Inject via FastAPI `Depends()`.
"""

from collections.abc import AsyncIterator

import structlog
from fastapi import Depends
from langchain_core.language_models import BaseChatModel
from langchain_core.messages import BaseMessage, HumanMessage

from app.infrastructure.llm import BaseLLMProvider, get_llm_provider_dependency

logger = structlog.get_logger(__name__)


class LLMService:
    """High-level chat operations backed by the configured LLM provider."""

    def __init__(
        self,
        provider: BaseLLMProvider = Depends(get_llm_provider_dependency),
    ) -> None:
        self.provider = provider

    def _chat_model(self) -> BaseChatModel:
        return self.provider.get_chat_model()

    async def generate(self, prompt: str) -> str:
        """Generate a single completion for a prompt string."""
        model = self._chat_model()
        logger.info("llm_generate", provider=self.provider.provider_name)
        response = await model.ainvoke([HumanMessage(content=prompt)])
        return self._as_text(response)

    async def stream(self, prompt: str) -> AsyncIterator[str]:
        """Stream a completion token-by-token for a prompt string."""
        model = self._chat_model()
        logger.info("llm_stream", provider=self.provider.provider_name)
        async for chunk in model.astream([HumanMessage(content=prompt)]):
            text = self._as_text(chunk)
            if text:
                yield text

    @staticmethod
    def _as_text(message: BaseMessage) -> str:
        """Coerce a LangChain message's content to a plain string."""
        content = message.content
        if isinstance(content, str):
            return content
        # Content can be a list of parts (text/blocks); join the text parts.
        parts: list[str] = []
        for part in content:
            if isinstance(part, str):
                parts.append(part)
            elif isinstance(part, dict) and part.get("type") == "text":
                parts.append(str(part.get("text", "")))
        return "".join(parts)
