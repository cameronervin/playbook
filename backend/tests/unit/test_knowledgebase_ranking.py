from __future__ import annotations

from app.infrastructure.knowledgebase.ranking import rank_retrieved_chunks
from app.schemas.knowledgebase import RetrievedChunk


def _chunk(
    title: str,
    *,
    score: float,
    source_date: str | None = None,
    is_official: bool = False,
    priority: int = 0,
) -> RetrievedChunk:
    return RetrievedChunk(
        text=f"{title} text",
        similarity_score=score,
        metadata={
            "source_title": title,
            "source_date": source_date,
            "is_official": is_official,
            "priority": priority,
        },
    )


def test_rank_retrieved_chunks_prefers_newer_source_within_relevance_band() -> None:
    ranked = rank_retrieved_chunks(
        [
            _chunk("Older top score", score=0.93, source_date="2026-01-01"),
            _chunk("Newer near match", score=0.91, source_date="2026-03-01"),
        ]
    )

    assert [chunk.metadata["source_title"] for chunk in ranked] == [
        "Newer near match",
        "Older top score",
    ]


def test_rank_retrieved_chunks_keeps_stronger_semantic_band_first() -> None:
    ranked = rank_retrieved_chunks(
        [
            _chunk("Relevant older source", score=0.93, source_date="2026-01-01"),
            _chunk("Stale lower band", score=0.87, source_date="2026-04-01"),
        ]
    )

    assert [chunk.metadata["source_title"] for chunk in ranked] == [
        "Relevant older source",
        "Stale lower band",
    ]


def test_rank_retrieved_chunks_ignores_official_and_priority_metadata() -> None:
    ranked = rank_retrieved_chunks(
        [
            _chunk(
                "Older high priority",
                score=0.92,
                source_date="2026-01-01",
                is_official=True,
                priority=100,
            ),
            _chunk(
                "Newer normal source",
                score=0.91,
                source_date="2026-02-01",
                is_official=False,
                priority=0,
            ),
        ]
    )

    assert [chunk.metadata["source_title"] for chunk in ranked] == [
        "Newer normal source",
        "Older high priority",
    ]
