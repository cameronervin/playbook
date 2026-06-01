"""Context assembly for knowledgebase retrieval results.

Formats RetrievedChunk instances into a markdown context string for injection
into LLM prompts, enforcing a token cap by truncating lower-scored chunks
first. Token estimation uses a chars/4 heuristic to avoid a tiktoken
dependency while remaining accurate enough for budget enforcement.

The assembled context is model-facing only.
"""
from __future__ import annotations

from app.schemas.knowledgebase import RetrievedChunk

_HEADER = """\
## Knowledge Base Context

The following information was retrieved from the knowledge base and may be relevant:

"""

_FOOTER = "\n\n---\nUse this context to inform — not replace — your analysis."

_CHARS_PER_TOKEN = 4


def _estimate_tokens(text: str) -> int:
    """Estimate token count using the chars/4 heuristic."""
    return max(1, len(text) // _CHARS_PER_TOKEN)


def _chunk_citation(chunk: RetrievedChunk) -> str:
    """Format a single chunk as a markdown citation block."""
    meta = chunk.metadata
    doc_title = meta.get("doc_title") or meta.get("filename") or "Unknown Source"
    section_path = meta.get("section_path") or meta.get("section") or ""

    source_label = f"{doc_title} — {section_path}" if section_path else doc_title
    score_str = f"{chunk.similarity_score:.0%}" if chunk.similarity_score is not None else "N/A"

    return f"### Source: {source_label}\n{chunk.text}\n(Relevance: {score_str})"


def assemble_context(chunks: list[RetrievedChunk], max_tokens: int) -> str:
    """Assemble retrieved chunks into a citation-formatted context string.

    Chunks are sorted by descending similarity score before assembly.
    Lower-scored chunks are truncated first when the total exceeds max_tokens.

    Args:
        chunks: Retrieved chunks from a search result.
        max_tokens: Maximum token budget (chars/4 estimation).

    Returns:
        Formatted markdown context string, or empty string if no chunks.
    """
    if not chunks:
        return ""

    sorted_chunks = sorted(
        chunks,
        key=lambda c: c.similarity_score if c.similarity_score is not None else 0.0,
        reverse=True,
    )

    fixed_overhead = _estimate_tokens(_HEADER + _FOOTER)
    remaining_budget = max_tokens - fixed_overhead

    sections: list[str] = []
    for chunk in sorted_chunks:
        citation = _chunk_citation(chunk)
        citation_tokens = _estimate_tokens(citation)

        if remaining_budget > 0 and citation_tokens <= remaining_budget:
            sections.append(citation)
            remaining_budget -= citation_tokens
        elif not sections:
            # Always include at least one result even if the budget is exhausted.
            char_limit = max(remaining_budget, 1) * _CHARS_PER_TOKEN
            sections.append(citation[:char_limit])
            break
        else:
            break

    if not sections:
        return ""

    body = "\n\n".join(sections)
    return _HEADER + body + _FOOTER
