"""OpenAI client builders for embedding (sync) flows.

Embedding clients use the sync ``OpenAI`` client — the worker runs on a threads
pool, where sync clients have no event-loop cleanup race (openai-python#1254)
AND reuse a single httpx connection pool, eliminating per-task TLS handshake
overhead.

Each builder is ``@lru_cache``d so a single client (and its connection pool) is
shared process-wide. ``from openai import OpenAI`` is imported lazily inside
each builder so this module compiles without ``openai`` installed.

NOTE: the source service also exposed an async ``get_vlm_client`` for the VLM
OCR path. That has been dropped along with the VLM provider — see
``app/infrastructure/STUBS.md``.
"""
from __future__ import annotations

from functools import lru_cache
from typing import TYPE_CHECKING

from app.core.config import settings

if TYPE_CHECKING:
    from openai import OpenAI

_ERR_DIRECT_KEY_REQUIRED = "OPENAI_API_KEY must be set when using direct provider mode"
_ERR_GATEWAY_URL_REQUIRED = "LLM_GATEWAY_BASE_URL must be set when using gateway provider mode"
_ERR_GATEWAY_KEY_REQUIRED = "LLM_GATEWAY_API_KEY must be set when using gateway provider mode"


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
def get_gateway_embed_client() -> "OpenAI":
    from openai import OpenAI

    if not settings.LLM_GATEWAY_BASE_URL:
        raise ValueError(_ERR_GATEWAY_URL_REQUIRED)
    if not settings.LLM_GATEWAY_API_KEY:
        raise ValueError(_ERR_GATEWAY_KEY_REQUIRED)
    return OpenAI(
        base_url=settings.LLM_GATEWAY_BASE_URL,
        api_key=settings.LLM_GATEWAY_API_KEY,
        timeout=settings.KB_EMBED_REQUEST_TIMEOUT_SECONDS,
        max_retries=0,
    )


def clear_client_caches() -> None:
    get_direct_embed_client.cache_clear()
    get_gateway_embed_client.cache_clear()
