"""Ranking and dedupe helpers for vector search results."""
from __future__ import annotations

from typing import Any

RANKING_STRATEGY_HYBRID = "hybrid"
DEDUPED_SEARCH_FETCH_MULTIPLIER = 3


def _merge_hybrid_candidates(
    *,
    semantic_results: list[dict],
    lexical_results: list[dict],
    max_docs: int,
    rrf_k: int,
) -> list[dict]:
    """Dedupe semantic/lexical candidates and rank with reciprocal rank fusion."""
    if max_docs <= 0:
        return []

    merged: dict[tuple[str, str], dict[str, Any]] = {}
    insertion_order = 0
    _record_ranked_candidates(
        merged=merged,
        results=semantic_results,
        score_key="semantic_score",
        rank_key="semantic_rank",
        insertion_order_start=insertion_order,
    )
    insertion_order += len(semantic_results)
    _record_ranked_candidates(
        merged=merged,
        results=lexical_results,
        score_key="lexical_score",
        rank_key="lexical_rank",
        insertion_order_start=insertion_order,
    )

    ranked_candidates: list[dict[str, Any]] = []
    for candidate in merged.values():
        semantic_rank = candidate.get("semantic_rank")
        lexical_rank = candidate.get("lexical_rank")
        hybrid_score = _rrf_score(semantic_rank, lexical_rank, rrf_k=rrf_k)
        result = dict(candidate["result"])
        metadata = dict(result.get("metadata") or {})
        metadata.update(
            {
                "semantic_score": candidate.get("semantic_score"),
                "semantic_rank": semantic_rank,
                "lexical_score": candidate.get("lexical_score"),
                "lexical_rank": lexical_rank,
                "hybrid_score": hybrid_score,
                "rerank_score": None,
                "ranking_strategy": RANKING_STRATEGY_HYBRID,
            }
        )
        result["metadata"] = metadata
        result["score"] = hybrid_score
        result["_hybrid_sort"] = (
            -hybrid_score,
            candidate["first_seen"],
        )
        ranked_candidates.append(result)

    ranked_candidates.sort(key=lambda item: item["_hybrid_sort"])
    final_results: list[dict] = []
    for item in ranked_candidates[:max_docs]:
        item.pop("_hybrid_sort", None)
        final_results.append(item)
    return final_results


def _record_ranked_candidates(
    *,
    merged: dict[tuple[str, str], dict[str, Any]],
    results: list[dict],
    score_key: str,
    rank_key: str,
    insertion_order_start: int,
) -> None:
    for offset, result in enumerate(results):
        key = _result_dedupe_key(result)
        if key is None:
            key = ("row", str(insertion_order_start + offset))
        if key not in merged:
            merged[key] = {
                "result": result,
                "first_seen": insertion_order_start + offset,
                "semantic_score": None,
                "semantic_rank": None,
                "lexical_score": None,
                "lexical_rank": None,
            }
        merged[key][score_key] = result.get("score")
        merged[key][rank_key] = offset + 1


def _result_dedupe_key(result: dict) -> tuple[str, str] | None:
    chunk_id = result.get("chunk_id") or (result.get("metadata") or {}).get("chunk_id")
    if chunk_id:
        return ("chunk_id", str(chunk_id))
    text = str(result.get("text", ""))
    if text:
        return ("text", text)
    return None


def _dedupe_fetch_limit(max_docs: int) -> int:
    return max_docs * DEDUPED_SEARCH_FETCH_MULTIPLIER


def dedupe_ranked_results(
    results: list[dict[str, Any]],
    *,
    max_docs: int,
) -> list[dict[str, Any]]:
    """Dedupe ranked search results while preserving first-seen order."""
    if max_docs <= 0:
        return []

    deduped: list[dict[str, Any]] = []
    seen: set[tuple[str, str]] = set()
    for result in results:
        key = _result_dedupe_key(result)
        if key is not None:
            if key in seen:
                continue
            seen.add(key)
        deduped.append(result)
        if len(deduped) >= max_docs:
            break
    return deduped


def _rrf_score(
    semantic_rank: int | None,
    lexical_rank: int | None,
    *,
    rrf_k: int,
) -> float:
    score = 0.0
    if semantic_rank is not None:
        score += 1.0 / (rrf_k + semantic_rank)
    if lexical_rank is not None:
        score += 1.0 / (rrf_k + lexical_rank)
    return score
