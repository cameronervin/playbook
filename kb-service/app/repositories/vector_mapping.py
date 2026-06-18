"""Search row mapping helpers for vector repositories."""
from __future__ import annotations

from typing import Any

from app.repositories.vector_records import (
    _deterministic_chunk_id,
    _int_or_none,
    _uuid_or_none,
)


def _map_search_row(row: dict[str, Any]) -> dict[str, Any] | None:
    """Map a raw search result row to the SearchResult-compatible dict shape."""
    raw_metadata = dict(row.get("cmetadata") or {})
    doc_id = _uuid_or_none(row.get("document_id") or raw_metadata.get("document_id"))
    if doc_id is None:
        return None
    kb_service_document_id = (
        _uuid_or_none(row.get("kb_service_document_id"))
        or _uuid_or_none(raw_metadata.get("kb_service_document_id"))
        or _uuid_or_none(raw_metadata.get("kb_document_id"))
        or doc_id
    )
    chunk_index = _int_or_none(row.get("chunk_index") or raw_metadata.get("chunk_index"))
    chunk_id = (
        _uuid_or_none(row.get("chunk_id"))
        or _uuid_or_none(raw_metadata.get("chunk_id"))
        or _uuid_or_none(row.get("embedding_id"))
    )
    if chunk_id is None and chunk_index is not None:
        chunk_id = _deterministic_chunk_id(kb_service_document_id, chunk_index)

    score = float(row.get("score", 0.0))
    metadata = {
        **raw_metadata,
        "document_id": str(doc_id),
        "kb_service_document_id": str(kb_service_document_id),
        "kb_document_id": str(kb_service_document_id),
        "score": score,
    }
    source_summary = row.get("source_summary")
    if source_summary is not None and "source_summary" not in metadata:
        metadata["source_summary"] = source_summary
    if chunk_id is not None:
        metadata["chunk_id"] = str(chunk_id)
    if chunk_index is not None:
        metadata["chunk_index"] = chunk_index

    return {
        "document_id": doc_id,
        "kb_service_document_id": kb_service_document_id,
        "chunk_id": chunk_id,
        "chunk_index": chunk_index,
        "text": row.get("document", ""),
        "score": score,
        "metadata": metadata,
    }
