"""OpenAI client builders for embedding (sync) flows.

Embedding clients use the sync ``OpenAI`` client — the worker runs on a threads
pool, where sync clients have no event-loop cleanup race (openai-python#1254)
AND reuse a single httpx connection pool, eliminating per-task TLS handshake
overhead.

Each builder is ``@lru_cache``d so a single client (and its connection pool) is
shared process-wide. ``from openai import OpenAI`` is imported lazily inside
each builder so this module compiles without ``openai`` installed. The VLM OCR
provider builds its own LiteLLM chat client because it has different timeout
and lifecycle needs than embeddings.
"""
from __future__ import annotations

from functools import lru_cache
from typing import TYPE_CHECKING

from app.core.config import settings

if TYPE_CHECKING:
    from openai import OpenAI

_ERR_DIRECT_KEY_REQUIRED = "OPENAI_API_KEY must be set when using direct provider mode"
_ERR_LITELLM_URL_REQUIRED = "LITELLM_BASE_URL must be set when using LiteLLM mode"
_ERR_LITELLM_KEY_REQUIRED = "LITELLM_API_KEY must be set when using LiteLLM mode"


@lru_cache
def get_direct_embed_client() -> "OpenAI":
    from openai import OpenAI

    if not settings.OPENAI_API_KEY:
        raise ValueError(_ERR_DIRECT_KEY_REQUIRED)
    return OpenAI(
        api_key=settings.OPENAI_API_KEY,
        timeout=settings.KB_EMBED_REQUEST_TIMEOUT_SECONDS,
        max_retries=0,
    )


@lru_cache
def get_litellm_embed_client() -> "OpenAI":
    from openai import OpenAI

    if not settings.LITELLM_BASE_URL:
        raise ValueError(_ERR_LITELLM_URL_REQUIRED)
    if not settings.LITELLM_API_KEY:
        raise ValueError(_ERR_LITELLM_KEY_REQUIRED)
    return OpenAI(
        base_url=settings.LITELLM_BASE_URL,
        api_key=settings.LITELLM_API_KEY,
        timeout=settings.KB_EMBED_REQUEST_TIMEOUT_SECONDS,
        max_retries=0,
    )


def clear_client_caches() -> None:
    get_direct_embed_client.cache_clear()
    get_litellm_embed_client.cache_clear()
