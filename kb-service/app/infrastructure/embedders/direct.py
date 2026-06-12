"""Direct OpenAI embedding provider."""
from __future__ import annotations

from typing import TYPE_CHECKING

from app.core.config import settings
from app.infrastructure.embedders.base import BaseEmbedProvider

if TYPE_CHECKING:
    from openai import OpenAI


class DirectEmbedProvider(BaseEmbedProvider):
    """Calls OpenAI /v1/embeddings directly with an injected sync OpenAI client."""

    def __init__(self, client: "OpenAI") -> None:
        super().__init__(client, settings.DIRECT_EMBED_MODEL)

    @property
    def provider_name(self) -> str:
        return "direct"
