"""Base reranker provider contract and DTOs."""
from __future__ import annotations

import uuid
from abc import ABC, abstractmethod
from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class RerankCandidate:
    """A candidate chunk submitted to the cross-encoder reranker."""

    original_index: int
    chunk_id: uuid.UUID | str | None
    text: str


@dataclass(frozen=True, slots=True)
class RerankedCandidate:
    """A reranker result mapped back to the original candidate identity."""

    candidate: RerankCandidate
    rerank_score: float | None
    rank: int


class RerankProviderError(RuntimeError):
    """Base exception for reranker provider failures."""


class RerankTransientError(RerankProviderError):
    """Retryable upstream failure such as timeout, transport error, or 5xx."""


class BaseRerankProvider(ABC):
    """Abstract reranker provider interface."""

    @property
    @abstractmethod
    def provider_name(self) -> str:
        ...

    @abstractmethod
    def rerank(
        self,
        *,
        query: str,
        candidates: list[RerankCandidate],
        top_n: int | None = None,
    ) -> list[RerankedCandidate]:
        ...
