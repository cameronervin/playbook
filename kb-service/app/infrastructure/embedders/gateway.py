"""Gateway (LiteLLM) embedding provider."""
from __future__ import annotations

from typing import TYPE_CHECKING

from app.core.config import settings
from app.infrastructure.embedders.base import BaseEmbedProvider

if TYPE_CHECKING:
    from openai import OpenAI


class GatewayEmbedProvider(BaseEmbedProvider):
    """Calls the LiteLLM gateway for embeddings with an injected sync OpenAI client."""

    def __init__(self, client: "OpenAI") -> None:
        super().__init__(client, settings.LLM_GATEWAY_EMBED_MODEL)

    @property
    def provider_name(self) -> str:
        return "gateway"
