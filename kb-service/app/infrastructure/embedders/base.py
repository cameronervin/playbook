"""Base embedding provider interface.

Pattern overview:
  * ``EmbedProviderMode`` is a ``StrEnum`` (LITELLM/DIRECT) selecting how
    embeddings are produced.
  * ``BaseEmbedProvider`` is an ABC holding the shared sync ``embed()`` loop;
    subclasses only supply the injected ``OpenAI`` client + model name and the
    ``provider_name`` property.
  * The error hierarchy (``EmbedProviderError`` / ``EmbedRateLimitError`` /
    ``EmbedTransientError``) plus ``normalize_embed_exception`` map raw OpenAI
    SDK exceptions onto retry-aware domain exceptions so the worker's retry
    logic can act on them.

``OpenAI`` is imported only under ``TYPE_CHECKING`` (for annotations) — the
actual SDK exception classes are imported lazily inside
``normalize_embed_exception`` — so this module compiles without ``openai``
installed.
"""
from __future__ import annotations

import time
import uuid
from abc import ABC, abstractmethod
from dataclasses import dataclass
from enum import StrEnum
from typing import TYPE_CHECKING

import structlog

from app.core.config import settings

if TYPE_CHECKING:
    from openai import OpenAI

logger = structlog.get_logger(__name__)


class EmbedProviderMode(StrEnum):
    LITELLM = "litellm"
    DIRECT = "direct"


@dataclass(frozen=True)
class EmbedErrorContext:
    """Structured gateway/SDK failure — attached to raised embed exceptions."""

    status_code: int | None = None
    response_body: str | None = None
    response_headers: dict[str, str] | None = None
    gateway_error: dict[str, str | None] | None = None
    request_id: str | None = None


class EmbedProviderError(RuntimeError):
    """Base for normalized embed failures — carries HTTP context for task logs."""

    def __init__(
        self,
        message: str,
        *,
        error_context: EmbedErrorContext | None = None,
    ) -> None:
        super().__init__(message)
        ctx = error_context or EmbedErrorContext()
        self.error_context = ctx
        self.status_code = ctx.status_code
        self.response_body = ctx.response_body
        self.gateway_error = ctx.gateway_error
        self.request_id = ctx.request_id


class EmbedRateLimitError(EmbedProviderError):
    """Retryable exception — provider returned HTTP 429."""

    def __init__(
        self,
        message: str,
        retry_after_seconds: float | None = None,
        *,
        error_context: EmbedErrorContext | None = None,
    ) -> None:
        super().__init__(message, error_context=error_context)
        self.retry_after_seconds = retry_after_seconds


class EmbedTransientError(EmbedProviderError):
    """Retryable exception — transient upstream failure (5xx, timeout, etc.)."""


class BaseEmbedProvider(ABC):
    """Abstract base for all embedding providers.

    Subclasses supply the injected sync OpenAI client and the model name;
    the shared embed() loop lives here to avoid duplication.

    Why sync (not AsyncOpenAI)? The worker uses a threads pool. Each task
    already runs on its own thread, so async buys us nothing per call. Worse,
    creating an AsyncOpenAI per task + asyncio.run() created event-loop cleanup
    races (see openai-python#1254) that bubbled up as spurious "Connection
    error" failures during httpx connection-pool teardown. The sync client
    reuses a single httpx connection pool across all tasks sharing this provider
    instance — fewer TLS handshakes, no event-loop bugs.
    """

    def __init__(self, client: "OpenAI", model_name: str) -> None:
        self._client = client
        self._model_name = model_name

    @property
    @abstractmethod
    def provider_name(self) -> str:
        ...

    def embed(self, texts: list[str]) -> list[list[float]]:
        if not texts:
            return []

        # Per-call diagnostic context so logs can be correlated with the
        # gateway / SDK side.
        call_id = uuid.uuid4().hex[:12]
        total_chars = sum(len(t) for t in texts)
        request_started_at = time.perf_counter()

        logger.info(
            "embed_request_started",
            call_id=call_id,
            provider=self.provider_name,
            model=self._model_name,
            input_count=len(texts),
            total_chars=total_chars,
        )

        try:
            response = self._client.embeddings.create(
                model=self._model_name,
                input=texts,
                encoding_format="float",
            )
        except Exception as exc:
            elapsed_ms = int((time.perf_counter() - request_started_at) * 1000)
            logger.error(
                "embed_request_failed",
                call_id=call_id,
                provider=self.provider_name,
                model=self._model_name,
                input_count=len(texts),
                total_chars=total_chars,
                elapsed_ms=elapsed_ms,
                exception_class=type(exc).__name__,
                exception_message=str(exc),
            )
            raise normalize_embed_exception(exc) from exc

        elapsed_ms = int((time.perf_counter() - request_started_at) * 1000)

        embeddings: list[list[float]] = []
        for item in response.data:
            vector = list(item.embedding)
            if len(vector) != settings.KB_EMBED_DIMENSIONS:
                raise ValueError(
                    f"Unexpected embedding dimensions: {len(vector)} "
                    f"(expected {settings.KB_EMBED_DIMENSIONS})"
                )
            embeddings.append(vector)

        logger.info(
            "embed_request_ok",
            call_id=call_id,
            provider=self.provider_name,
            model=self._model_name,
            input_count=len(texts),
            total_chars=total_chars,
            embedding_count=len(embeddings),
            elapsed_ms=elapsed_ms,
        )
        return embeddings

    def health_check(self) -> bool:
        return True


def normalize_embed_exception(exc: Exception) -> Exception:
    """Map openai SDK exceptions to retry-aware provider exceptions.

    The wrapped exception's str() is the RAW SDK message — no decoration, no
    interpretation. Whatever the gateway / SDK said is surfaced into the
    worker's retry log line. SDK exception classes are imported lazily so this
    module compiles without ``openai`` installed.
    """
    try:
        from openai import (
            APIConnectionError,
            APIStatusError,
            APITimeoutError,
            RateLimitError,
        )
    except Exception:
        # openai not installed — nothing to normalize.
        return exc

    if isinstance(exc, RateLimitError):
        retry_after: float | None = None
        response = getattr(exc, "response", None)
        headers = getattr(response, "headers", None)
        if isinstance(headers, dict):
            header_val = headers.get("retry-after")
            if header_val is not None:
                try:
                    retry_after = float(header_val)
                except (TypeError, ValueError):
                    pass
        return EmbedRateLimitError(str(exc), retry_after)

    if isinstance(exc, APITimeoutError):
        return EmbedTransientError(str(exc))
    if isinstance(exc, APIConnectionError):
        return EmbedTransientError(str(exc))

    if isinstance(exc, APIStatusError):
        status = exc.status_code
        if status == 429:
            return EmbedRateLimitError(str(exc))
        if status in {408, 409, 500, 502, 503, 504}:
            return EmbedTransientError(str(exc))

    return exc
