"""Deterministic ranking policy for retrieved KB chunks."""

from __future__ import annotations

from datetime import date
from math import floor
from typing import Any

from app.schemas.knowledgebase import RetrievedChunk

RELEVANCE_BAND_WIDTH = 0.05


def rank_retrieved_chunks(chunks: list[RetrievedChunk]) -> list[RetrievedChunk]:
    """Rank chunks by semantic relevance band, then source freshness.

    KB-service already filters by score threshold. The backend applies the MVP
    conflict rule: when sources are near-similar, prefer newer applicable
    source_date. Official and priority metadata are intentionally ignored.
    """
    if not chunks:
        return []

    top_score = max(_score(chunk) for chunk in chunks)
    indexed = list(enumerate(chunks))
    return [
        chunk
        for _, chunk in sorted(
            indexed,
            key=lambda item: (
                _relevance_band(top_score, _score(item[1])),
                _date_sort_value(item[1].metadata.get("source_date")),
                -_score(item[1]),
                item[0],
            ),
        )
    ]


def _score(chunk: RetrievedChunk) -> float:
    return float(chunk.similarity_score or 0.0)


def _relevance_band(top_score: float, score: float) -> int:
    return max(0, floor((top_score - score) / RELEVANCE_BAND_WIDTH))


def _date_sort_value(value: Any) -> int:
    parsed = _parse_source_date(value)
    if parsed is None:
        return 0
    return -parsed.toordinal()


def _parse_source_date(value: Any) -> date | None:
    if isinstance(value, date):
        return value
    if not isinstance(value, str) or not value.strip():
        return None
    try:
        return date.fromisoformat(value.strip())
    except ValueError:
        return None
