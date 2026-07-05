"""Canonical reranker provider factory."""
from __future__ import annotations

from functools import lru_cache

import structlog

from app.core.config import settings
from app.infrastructure.llm.builder import (
    close_litellm_rerank_client,
    get_litellm_rerank_client,
)
from app.infrastructure.rerankers.base import BaseRerankProvider
from app.infrastructure.rerankers.litellm import LiteLLMRerankProvider

logger = structlog.get_logger(__name__)


@lru_cache
def get_rerank_provider() -> BaseRerankProvider:
    """Process-wide LiteLLM reranker provider singleton."""
    logger.info(
        "kb_rerank_provider_init",
        provider="litellm",
        model=settings.LITELLM_RERANK_MODEL,
        fail_open=settings.KB_RERANK_FAIL_OPEN,
    )
    return LiteLLMRerankProvider(
        client=get_litellm_rerank_client(),
        model_name=settings.LITELLM_RERANK_MODEL,
        fail_open=settings.KB_RERANK_FAIL_OPEN,
    )


def clear_all_caches() -> None:
    get_rerank_provider.cache_clear()
    close_litellm_rerank_client()


__all__ = ["get_rerank_provider", "clear_all_caches"]
