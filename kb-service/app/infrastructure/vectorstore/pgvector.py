"""pgvector helpers (wrappers around SQLAlchemy expressions).

These module-level functions keep stable signatures for tests and callers while
delegating SQL construction to the vector repository (no hand-written SQL
strings here). The repository builds the search statement with pgvector's
``.cosine_distance()``; relevance is reported as ``score = 1 - distance`` and an
optional ``metadata_filter`` is applied via JSONB containment.

The ``VectorEmbedding`` model and focused vector repository helper modules own
the SQL construction and row mapping details.
"""
from __future__ import annotations

import uuid
from typing import TYPE_CHECKING, Any

import structlog
from sqlalchemy import delete, insert

from app.models.vector_embedding import VectorEmbedding
from app.repositories.vector_mapping import _map_search_row
from app.repositories.vector_queries import _build_search_statement
from app.repositories.vector_records import _build_chunk_records

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

logger = structlog.get_logger(__name__)


def bulk_insert_embeddings(
    pg_engine,
    document_id: uuid.UUID,
    collection_id: uuid.UUID,
    chunks: list[dict],
    embeddings: list[list[float]],
) -> None:
    """Delete existing embeddings for document_id then insert chunk vectors."""
    records = _build_chunk_records(
        document_id=document_id,
        collection_id=collection_id,
        chunks=chunks,
        embeddings=embeddings,
    )

    with pg_engine.begin() as conn:
        conn.execute(
            delete(VectorEmbedding).where(
                VectorEmbedding.cmetadata["document_id"].astext == str(document_id)
            )
        )
        if records:
            conn.execute(insert(VectorEmbedding), records)


def cosine_search(
    pg_engine,
    collection_id: uuid.UUID,
    organization_id: uuid.UUID,
    query_vector: list[float],
    max_docs: int,
    score_threshold: float,
    metadata_filter: dict[str, Any] | None = None,
) -> list[dict]:
    """HNSW cosine similarity search against the embeddings table."""
    if max_docs <= 0:
        return []

    statement = _build_search_statement(
        collection_id=collection_id,
        query_vector=query_vector,
        max_docs=max_docs,
        score_threshold=score_threshold,
        organization_id=organization_id,
        metadata_filter=metadata_filter,
    )

    with pg_engine.begin() as conn:
        rows = conn.execute(statement).mappings().all()

    results: list[dict[str, Any]] = []
    for row in rows:
        mapped = _map_search_row(row)
        if mapped is not None:
            results.append(mapped)
    return results


async def async_cosine_search(
    session: "AsyncSession",
    collection_id: uuid.UUID,
    organization_id: uuid.UUID,
    query_vector: list[float],
    max_docs: int,
    score_threshold: float,
    metadata_filter: dict[str, Any] | None = None,
) -> list[dict]:
    """HNSW cosine similarity search using an AsyncSession (non-blocking)."""
    if max_docs <= 0:
        return []

    statement = _build_search_statement(
        collection_id=collection_id,
        query_vector=query_vector,
        max_docs=max_docs,
        score_threshold=score_threshold,
        organization_id=organization_id,
        metadata_filter=metadata_filter,
    )

    result = await session.execute(statement)
    rows = result.mappings().all()

    results: list[dict[str, Any]] = []
    for row in rows:
        mapped = _map_search_row(row)
        if mapped is not None:
            results.append(mapped)
    return results
