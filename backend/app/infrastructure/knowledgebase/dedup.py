"""Content-based deduplication for retrieved knowledgebase chunks.

When a backend returns multiple ingestion versions of the same document,
identical content can appear more than once with different metadata. This
wastes token budget and reduces diversity in the assembled LLM context.

``deduplicate_chunks`` removes duplicates by content, keeping the
highest-scored instance per unique passage. It does not sort — sorting is the
responsibility of ``assemble_context()``.
"""
from __future__ import annotations

from app.schemas.knowledgebase import RetrievedChunk


def deduplicate_chunks(chunks: list[RetrievedChunk]) -> list[RetrievedChunk]:
    """Remove duplicate chunks by text content, keeping the highest-scored instance.

    Args:
        chunks: Retrieved chunks, possibly containing duplicates.

    Returns:
        Deduplicated list preserving first-seen insertion order.
    """
    if not chunks:
        return []

    seen: dict[str, RetrievedChunk] = {}
    for chunk in chunks:
        existing = seen.get(chunk.text)
        if existing is None:
            seen[chunk.text] = chunk
        else:
            existing_score = existing.similarity_score or 0.0
            new_score = chunk.similarity_score or 0.0
            if new_score > existing_score:
                seen[chunk.text] = chunk
    return list(seen.values())
