"""Chunk record builders for vector persistence."""
from __future__ import annotations

import uuid
from typing import Any

_CHUNK_ID_NAMESPACE = uuid.uuid5(uuid.NAMESPACE_URL, "playbook.kb-service.chunk")
_SENTINEL = object()


def _build_chunk_records(
    *,
    document_id: uuid.UUID,
    collection_id: uuid.UUID,
    chunks: list[dict],
    embeddings: list[list[float]],
    chunk_index_offset: int = 0,
) -> list[dict[str, Any]]:
    """Eager list builder retained for non-streaming callers."""
    if len(chunks) != len(embeddings):
        raise ValueError("chunks and embeddings must have the same length")
    return list(
        _iter_chunk_records(
            document_id=document_id,
            collection_id=collection_id,
            chunks=chunks,
            embeddings=embeddings,
            chunk_index_offset=chunk_index_offset,
        )
    )


def _deterministic_chunk_id(document_id: uuid.UUID, chunk_index: int) -> uuid.UUID:
    """Return a stable chunk UUID for a document/index pair."""
    return uuid.uuid5(_CHUNK_ID_NAMESPACE, f"{document_id}:{chunk_index}")


def _uuid_or_none(value: Any) -> uuid.UUID | None:
    if value in (None, ""):
        return None
    try:
        return uuid.UUID(str(value))
    except (TypeError, ValueError):
        return None


def _int_or_none(value: Any) -> int | None:
    if value in (None, ""):
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _normalize_chunk_metadata(
    *,
    document_id: uuid.UUID,
    chunk_metadata: dict[str, Any],
    chunk_index: int,
) -> dict[str, Any]:
    kb_service_document_id = (
        _uuid_or_none(chunk_metadata.get("kb_service_document_id"))
        or _uuid_or_none(chunk_metadata.get("kb_document_id"))
        or document_id
    )
    chunk_id = _deterministic_chunk_id(kb_service_document_id, chunk_index)
    if chunk_metadata.get("source_type") == "conversation_file":
        conversation_file_id = (
            _uuid_or_none(chunk_metadata.get("conversation_file_id"))
            or _uuid_or_none(chunk_metadata.get("document_id"))
            or kb_service_document_id
        )
        return {
            **chunk_metadata,
            "document_id": str(conversation_file_id),
            "conversation_file_id": str(conversation_file_id),
            "kb_service_document_id": str(kb_service_document_id),
            "kb_document_id": str(kb_service_document_id),
            "chunk_id": str(chunk_id),
            "chunk_index": chunk_index,
        }

    playbook_document_id = (
        _uuid_or_none(chunk_metadata.get("playbook_document_id"))
        or _uuid_or_none(chunk_metadata.get("document_id"))
        or kb_service_document_id
    )

    return {
        **chunk_metadata,
        "document_id": str(playbook_document_id),
        "playbook_document_id": str(playbook_document_id),
        "kb_service_document_id": str(kb_service_document_id),
        "kb_document_id": str(kb_service_document_id),
        "chunk_id": str(chunk_id),
        "chunk_index": chunk_index,
    }


def _iter_chunk_records(
    *,
    document_id: uuid.UUID,
    collection_id: uuid.UUID,
    chunks,
    embeddings,
    chunk_index_offset: int = 0,
):
    """Yield insertable record dicts one at a time."""
    chunks_iter = iter(chunks)
    embeds_iter = iter(embeddings)
    index = 0
    for chunk in chunks_iter:
        try:
            embedding = next(embeds_iter)
        except StopIteration as exc:
            raise ValueError(
                f"chunks/embeddings length mismatch - exhausted embeddings at chunk index {index}"
            ) from exc

        chunk_text = chunk.get("text")
        chunk_metadata = chunk.get("metadata", {})
        if not isinstance(chunk_text, str):
            raise TypeError("Each chunk must contain a string text field")
        if not isinstance(chunk_metadata, dict):
            raise TypeError("Each chunk metadata field must be a dict")

        global_chunk_index = chunk_index_offset + index
        metadata = _normalize_chunk_metadata(
            document_id=document_id,
            chunk_metadata=chunk_metadata,
            chunk_index=global_chunk_index,
        )
        yield {
            "collection_id": collection_id,
            "embedding": embedding,
            "document": chunk_text,
            "cmetadata": metadata,
        }
        index += 1

    leftover = next(embeds_iter, _SENTINEL)
    if leftover is not _SENTINEL:
        raise ValueError(
            f"chunks/embeddings length mismatch - {index} chunks consumed but embeddings still has data"
        )
