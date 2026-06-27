"""SQL statement builders for vector search repositories."""
from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy import Integer, cast, func, or_, select
from sqlalchemy.dialects.postgresql import UUID

from app.models.document import Document
from app.models.vector_embedding import VectorEmbedding

SEARCHABLE_DOCUMENT_STATUS = "success"


def _document_metadata_match(document_id: uuid.UUID):
    document_id_value = str(document_id)
    return or_(
        VectorEmbedding.cmetadata["kb_service_document_id"].astext == document_id_value,
        VectorEmbedding.cmetadata["kb_document_id"].astext == document_id_value,
        VectorEmbedding.cmetadata["document_id"].astext == document_id_value,
    )


def _build_search_common(
    *,
    collection_id: uuid.UUID,
    organization_id: uuid.UUID | str,
    metadata_filter: dict[str, Any] | None,
    metadata_filters: list[dict[str, Any]] | None = None,
) -> tuple[
    Any,
    Any,
    Any,
    Any,
    list[Any],
]:
    metadata = VectorEmbedding.cmetadata
    document_id_expr = func.cast(
        metadata["document_id"].astext,
        UUID(as_uuid=True),
    )
    kb_service_document_id_expr = func.cast(
        func.coalesce(
            metadata["kb_service_document_id"].astext,
            metadata["kb_document_id"].astext,
            metadata["document_id"].astext,
        ),
        UUID(as_uuid=True),
    )
    chunk_id_expr = func.cast(
        metadata["chunk_id"].astext,
        UUID(as_uuid=True),
    )
    chunk_index_expr = cast(metadata["chunk_index"].astext, Integer)

    conditions = [
        VectorEmbedding.collection_id == collection_id,
        Document.status == SEARCHABLE_DOCUMENT_STATUS,
        VectorEmbedding.cmetadata.contains({"organization_id": str(organization_id)}),
    ]
    if metadata_filters:
        conditions.append(
            or_(
                *(
                    VectorEmbedding.cmetadata.contains(filter_item)
                    for filter_item in metadata_filters
                )
            )
        )
    elif metadata_filter:
        conditions.append(VectorEmbedding.cmetadata.contains(metadata_filter))

    return (
        document_id_expr,
        kb_service_document_id_expr,
        chunk_id_expr,
        chunk_index_expr,
        conditions,
    )


def _build_search_statement(
    *,
    collection_id: uuid.UUID,
    query_vector: list[float],
    max_docs: int,
    score_threshold: float,
    organization_id: uuid.UUID | str,
    metadata_filter: dict[str, Any] | None,
    metadata_filters: list[dict[str, Any]] | None = None,
):
    """Build the cosine-distance similarity SELECT shared by both repos."""
    distance_expr = VectorEmbedding.embedding.cosine_distance(query_vector)
    (
        document_id_expr,
        kb_service_document_id_expr,
        chunk_id_expr,
        chunk_index_expr,
        conditions,
    ) = _build_search_common(
        collection_id=collection_id,
        organization_id=organization_id,
        metadata_filter=metadata_filter,
        metadata_filters=metadata_filters,
    )
    distance_threshold = max(0.0, 1.0 - score_threshold)
    conditions.append(distance_expr <= distance_threshold)

    score_expr = (1.0 - distance_expr).label("score")
    return (
        select(
            VectorEmbedding.id.label("embedding_id"),
            document_id_expr.label("document_id"),
            kb_service_document_id_expr.label("kb_service_document_id"),
            chunk_id_expr.label("chunk_id"),
            chunk_index_expr.label("chunk_index"),
            VectorEmbedding.document.label("document"),
            Document.summary.label("source_summary"),
            VectorEmbedding.cmetadata.label("cmetadata"),
            score_expr,
        )
        .select_from(VectorEmbedding)
        .join(Document, Document.id == kb_service_document_id_expr)
        .where(*conditions)
        .order_by(distance_expr)
        .limit(max_docs)
    )


def _build_lexical_search_statement(
    *,
    collection_id: uuid.UUID,
    query_text: str,
    max_docs: int,
    organization_id: uuid.UUID | str,
    metadata_filter: dict[str, Any] | None,
    metadata_filters: list[dict[str, Any]] | None = None,
):
    """Build the PostgreSQL full-text lexical SELECT."""
    (
        document_id_expr,
        kb_service_document_id_expr,
        chunk_id_expr,
        chunk_index_expr,
        conditions,
    ) = _build_search_common(
        collection_id=collection_id,
        organization_id=organization_id,
        metadata_filter=metadata_filter,
        metadata_filters=metadata_filters,
    )
    query_expr = func.websearch_to_tsquery("english", query_text)
    match_expr = VectorEmbedding.search_vector.bool_op("@@")(query_expr)
    score_expr = func.ts_rank_cd(VectorEmbedding.search_vector, query_expr).label(
        "score"
    )
    conditions.append(match_expr)

    return (
        select(
            VectorEmbedding.id.label("embedding_id"),
            document_id_expr.label("document_id"),
            kb_service_document_id_expr.label("kb_service_document_id"),
            chunk_id_expr.label("chunk_id"),
            chunk_index_expr.label("chunk_index"),
            VectorEmbedding.document.label("document"),
            Document.summary.label("source_summary"),
            VectorEmbedding.cmetadata.label("cmetadata"),
            score_expr,
        )
        .select_from(VectorEmbedding)
        .join(Document, Document.id == kb_service_document_id_expr)
        .where(*conditions)
        .order_by(score_expr.desc(), VectorEmbedding.id)
        .limit(max_docs)
    )
