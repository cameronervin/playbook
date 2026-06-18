"""Compatibility facade for vector persistence and search repositories."""
from __future__ import annotations

from app.repositories.vector_async import AsyncVectorRepository
from app.repositories.vector_mapping import _map_search_row
from app.repositories.vector_queries import (
    SEARCHABLE_DOCUMENT_STATUS,
    _build_lexical_search_statement,
    _build_search_common,
    _build_search_statement,
    _document_metadata_match,
)
from app.repositories.vector_ranking import (
    DEDUPED_SEARCH_FETCH_MULTIPLIER,
    RANKING_STRATEGY_HYBRID,
    _dedupe_fetch_limit,
    _merge_hybrid_candidates,
    _record_ranked_candidates,
    _result_dedupe_key,
    _rrf_score,
    dedupe_ranked_results,
)
from app.repositories.vector_records import (
    _build_chunk_records,
    _deterministic_chunk_id,
    _int_or_none,
    _iter_chunk_records,
    _normalize_chunk_metadata,
    _uuid_or_none,
)
from app.repositories.vector_sync import VectorRepository, _slice_iter

__all__ = [
    "AsyncVectorRepository",
    "DEDUPED_SEARCH_FETCH_MULTIPLIER",
    "RANKING_STRATEGY_HYBRID",
    "SEARCHABLE_DOCUMENT_STATUS",
    "VectorRepository",
    "_build_chunk_records",
    "_build_lexical_search_statement",
    "_build_search_common",
    "_build_search_statement",
    "_dedupe_fetch_limit",
    "_deterministic_chunk_id",
    "_document_metadata_match",
    "_int_or_none",
    "_iter_chunk_records",
    "_map_search_row",
    "_merge_hybrid_candidates",
    "_normalize_chunk_metadata",
    "_record_ranked_candidates",
    "_result_dedupe_key",
    "_rrf_score",
    "_slice_iter",
    "_uuid_or_none",
    "dedupe_ranked_results",
]
