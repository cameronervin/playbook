"""LiteLLM /rerank provider."""
from __future__ import annotations

import time
import uuid
from typing import Any

import httpx
import structlog

from app.infrastructure.rerankers.base import (
    BaseRerankProvider,
    RerankCandidate,
    RerankedCandidate,
    RerankProviderError,
    RerankTransientError,
)

logger = structlog.get_logger(__name__)

_RERANK_PATH = "/rerank"
_RETRYABLE_STATUS_CODES = {408, 409, 429, 500, 502, 503, 504}


class LiteLLMRerankProvider(BaseRerankProvider):
    """Calls LiteLLM Proxy /rerank with an injected sync HTTPX client."""

    def __init__(
        self,
        *,
        client: Any,
        model_name: str,
        fail_open: bool,
    ) -> None:
        self._client = client
        self._model_name = model_name
        self._fail_open = fail_open

    @property
    def provider_name(self) -> str:
        return "litellm"

    def rerank(
        self,
        *,
        query: str,
        candidates: list[RerankCandidate],
        top_n: int | None = None,
    ) -> list[RerankedCandidate]:
        if not candidates:
            return []

        call_id = uuid.uuid4().hex[:12]
        bounded_top_n = _bounded_top_n(top_n, candidate_count=len(candidates))
        payload: dict[str, object] = {
            "model": self._model_name,
            "query": query,
            "documents": [candidate.text for candidate in candidates],
        }
        if bounded_top_n is not None:
            payload["top_n"] = bounded_top_n

        total_chars = sum(len(candidate.text) for candidate in candidates)
        request_started_at = time.perf_counter()
        logger.info(
            "kb_rerank_request_started",
            call_id=call_id,
            provider=self.provider_name,
            model=self._model_name,
            candidate_count=len(candidates),
            top_n=bounded_top_n,
            total_chars=total_chars,
        )

        try:
            response = self._client.post(_RERANK_PATH, json=payload)
        except (httpx.TimeoutException, httpx.TransportError) as exc:
            elapsed_ms = int((time.perf_counter() - request_started_at) * 1000)
            return self._handle_transient_failure(
                exc,
                call_id=call_id,
                candidates=candidates,
                top_n=bounded_top_n,
                total_chars=total_chars,
                elapsed_ms=elapsed_ms,
                status_code=None,
            )

        elapsed_ms = int((time.perf_counter() - request_started_at) * 1000)
        status_code = int(getattr(response, "status_code", 0) or 0)
        if status_code in _RETRYABLE_STATUS_CODES:
            return self._handle_transient_failure(
                RerankTransientError(f"LiteLLM rerank returned HTTP {status_code}"),
                call_id=call_id,
                candidates=candidates,
                top_n=bounded_top_n,
                total_chars=total_chars,
                elapsed_ms=elapsed_ms,
                status_code=status_code,
            )
        if status_code >= 400:
            logger.warning(
                "kb_rerank_request_failed",
                call_id=call_id,
                provider=self.provider_name,
                model=self._model_name,
                candidate_count=len(candidates),
                top_n=bounded_top_n,
                total_chars=total_chars,
                elapsed_ms=elapsed_ms,
                status_code=status_code,
                failure_class="RerankProviderError",
            )
            raise RerankProviderError(
                f"LiteLLM rerank returned non-retryable HTTP {status_code}"
            )

        results = self._parse_response(response, candidates=candidates)
        logger.info(
            "kb_rerank_request_ok",
            call_id=call_id,
            provider=self.provider_name,
            model=self._model_name,
            candidate_count=len(candidates),
            result_count=len(results),
            top_n=bounded_top_n,
            total_chars=total_chars,
            elapsed_ms=elapsed_ms,
            status_code=status_code,
        )
        return results

    def _handle_transient_failure(
        self,
        exc: Exception,
        *,
        call_id: str,
        candidates: list[RerankCandidate],
        top_n: int | None,
        total_chars: int,
        elapsed_ms: int,
        status_code: int | None,
    ) -> list[RerankedCandidate]:
        logger.warning(
            "kb_rerank_request_failed",
            call_id=call_id,
            provider=self.provider_name,
            model=self._model_name,
            candidate_count=len(candidates),
            top_n=top_n,
            total_chars=total_chars,
            elapsed_ms=elapsed_ms,
            status_code=status_code,
            failure_class=type(exc).__name__,
        )
        if not self._fail_open:
            raise RerankTransientError("LiteLLM rerank request failed") from exc

        logger.warning(
            "kb_rerank_fail_open",
            call_id=call_id,
            provider=self.provider_name,
            model=self._model_name,
            candidate_count=len(candidates),
            top_n=top_n,
            total_chars=total_chars,
            elapsed_ms=elapsed_ms,
            status_code=status_code,
            failure_class=type(exc).__name__,
        )
        return _input_order_results(candidates)

    def _parse_response(
        self,
        response: Any,
        *,
        candidates: list[RerankCandidate],
    ) -> list[RerankedCandidate]:
        try:
            payload = response.json()
        except Exception as exc:
            raise RerankProviderError("LiteLLM rerank response was not JSON") from exc

        if not isinstance(payload, dict):
            raise RerankProviderError("LiteLLM rerank response must be an object")
        raw_results = payload.get("results")
        if not isinstance(raw_results, list):
            raise RerankProviderError("LiteLLM rerank response missing results")

        seen_indexes: set[int] = set()
        mapped: list[RerankedCandidate] = []
        for rank, item in enumerate(raw_results, start=1):
            if not isinstance(item, dict):
                raise RerankProviderError("LiteLLM rerank result must be an object")
            if "index" not in item or "relevance_score" not in item:
                raise RerankProviderError(
                    "LiteLLM rerank result missing index or relevance_score"
                )
            index = _coerce_index(item["index"])
            if index < 0 or index >= len(candidates):
                raise RerankProviderError("LiteLLM rerank result index out of range")
            if index in seen_indexes:
                raise RerankProviderError("LiteLLM rerank result index duplicated")
            seen_indexes.add(index)
            score = _coerce_score(item["relevance_score"])
            mapped.append(
                RerankedCandidate(
                    candidate=candidates[index],
                    rerank_score=score,
                    rank=rank,
                )
            )
        return mapped


def _bounded_top_n(top_n: int | None, *, candidate_count: int) -> int | None:
    if top_n is None:
        return None
    return max(1, min(int(top_n), candidate_count))


def _coerce_index(value: object) -> int:
    try:
        return int(value)
    except (TypeError, ValueError) as exc:
        raise RerankProviderError("LiteLLM rerank result index is invalid") from exc


def _coerce_score(value: object) -> float:
    try:
        return float(value)
    except (TypeError, ValueError) as exc:
        raise RerankProviderError(
            "LiteLLM rerank result relevance_score is invalid"
        ) from exc


def _input_order_results(candidates: list[RerankCandidate]) -> list[RerankedCandidate]:
    return [
        RerankedCandidate(candidate=candidate, rerank_score=None, rank=rank)
        for rank, candidate in enumerate(candidates, start=1)
    ]
