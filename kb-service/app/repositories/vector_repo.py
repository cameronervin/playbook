"""Repository for kb.langchain_pg_* vector persistence + similarity search.

Two flavours, same SQL building blocks:
  * ``VectorRepository``      — sync; takes a sync ``Engine``; used by Celery
                                workers during ingestion (load-vector stage).
  * ``AsyncVectorRepository`` — async; takes an ``AsyncSession``; used by the
                                FastAPI search/ingest routes.

Both share the module-level ``_build_search_statement`` / ``_iter_chunk_records``
helpers so the cosine-distance similarity query is defined exactly once.
"""
from __future__ import annotations

import uuid
from typing import TYPE_CHECKING, Any

from sqlalchemy import Integer, cast, delete, func, insert, or_, select
from sqlalchemy.dialects.postgresql import UUID, insert as pg_insert

from app.models.configuration import Configuration
from app.models.document import Document
from app.models.vector_collection import VectorCollection
from app.models.vector_embedding import VectorEmbedding

if TYPE_CHECKING:
    from sqlalchemy.engine import Engine
    from sqlalchemy.ext.asyncio import AsyncSession


SEARCHABLE_DOCUMENT_STATUS = "success"
_CHUNK_ID_NAMESPACE = uuid.uuid5(uuid.NAMESPACE_URL, "playbook.kb-service.chunk")
RANKING_STRATEGY_HYBRID = "hybrid"


def _build_chunk_records(
    *,
    document_id: uuid.UUID,
    collection_id: uuid.UUID,
    chunks: list[dict],
    embeddings: list[list[float]],
    chunk_index_offset: int = 0,
) -> list[dict[str, Any]]:
    """Eager list builder retained for non-streaming callers (search path, tests)."""
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


def _document_metadata_match(document_id: uuid.UUID):
    document_id_value = str(document_id)
    return or_(
        VectorEmbedding.cmetadata["kb_service_document_id"].astext == document_id_value,
        VectorEmbedding.cmetadata["kb_document_id"].astext == document_id_value,
        VectorEmbedding.cmetadata["document_id"].astext == document_id_value,
    )


def _iter_chunk_records(
    *,
    document_id: uuid.UUID,
    collection_id: uuid.UUID,
    chunks,
    embeddings,
    chunk_index_offset: int = 0,
):
    """Yield insertable record dicts one-at-a-time.

    Generator-based to keep peak memory low during bulk INSERT: SQLAlchemy can
    feed records straight from the iterator into `conn.execute(insert(...))`
    batches without us first building the full records list. Pairs with
    `_slice_iter` which slices the generator into KB_VECTOR_INSERT_BATCH_SIZE
    sub-batches.

    Validation is per-element rather than upfront length check so the generator
    fails fast on bad input instead of after materialising everything.
    """
    chunks_iter = iter(chunks)
    embeds_iter = iter(embeddings)
    index = 0
    for chunk in chunks_iter:
        try:
            embedding = next(embeds_iter)
        except StopIteration as exc:
            raise ValueError(
                f"chunks/embeddings length mismatch — exhausted embeddings at chunk index {index}"
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

    # Tail check: embeddings shouldn't have leftovers.
    leftover = next(embeds_iter, _SENTINEL)
    if leftover is not _SENTINEL:
        raise ValueError(
            f"chunks/embeddings length mismatch — {index} chunks consumed but embeddings still has data"
        )


_SENTINEL = object()


def _slice_iter(iterator, batch_size: int):
    """Yield successive lists of up to `batch_size` elements drained from an iterator.

    Lets `conn.execute(insert(...), batch)` consume a stream without ever
    materialising the full record list. Empty trailing batch is suppressed.
    """
    batch: list = []
    for item in iterator:
        batch.append(item)
        if len(batch) >= batch_size:
            yield batch
            batch = []
    if batch:
        yield batch


def _map_search_row(row: dict[str, Any]) -> dict[str, Any] | None:
    """Map a raw search result row to the SearchResult-compatible dict shape.

    Renames the storage columns to the API contract: document -> text,
    cmetadata -> metadata. Returns None for rows without a document_id.
    """
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
        VectorEmbedding.cmetadata.contains(
            {"organization_id": str(organization_id)}
        ),
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
    """Build the cosine-distance similarity SELECT shared by both repos.

    score = 1 - cosine_distance, so a score_threshold maps to a maximum
    allowable distance of (1 - score_threshold). Rows are ordered by ascending
    distance (most similar first) and capped at max_docs.
    """
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
    """Build the PostgreSQL full-text lexical SELECT.

    Lexical search uses the generated ``search_vector`` column and mirrors the
    semantic path's collection/status/org/source-scope filters.
    """
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
        key = _candidate_dedupe_key(result)
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


def _candidate_dedupe_key(result: dict) -> tuple[str, str]:
    chunk_id = result.get("chunk_id") or (result.get("metadata") or {}).get("chunk_id")
    if chunk_id:
        return ("chunk_id", str(chunk_id))
    return ("text", str(result.get("text", "")))


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


class VectorRepository:
    """Sync vector persistence + search — used by Celery worker tasks.

    Takes a sync SQLAlchemy ``Engine`` (workers run on a threads pool, not an
    asyncio loop, so sync I/O is the natural fit here).
    """

    def __init__(self, pg_engine: "Engine") -> None:
        self._pg_engine = pg_engine

    def get_or_create_collection_id(self, collection_name: str) -> uuid.UUID:
        with self._pg_engine.begin() as conn:
            statement = (
                pg_insert(VectorCollection)
                .values(name=collection_name, cmetadata={})
                .on_conflict_do_update(
                    index_elements=[VectorCollection.name],
                    set_={"name": collection_name},
                )
                .returning(VectorCollection.uuid)
            )
            collection_row = conn.execute(statement).mappings().first()
            if not collection_row:
                raise RuntimeError("Could not resolve vector collection id")
            return collection_row["uuid"]

    def resolve_collection_id_for_configuration(self, configuration_id: uuid.UUID) -> uuid.UUID:
        with self._pg_engine.begin() as conn:
            config_row = conn.execute(
                select(Configuration.collection_name).where(
                    Configuration.id == configuration_id
                )
            ).mappings().first()
            if not config_row:
                raise LookupError(f"Configuration not found: {configuration_id}")
            collection_name = config_row["collection_name"]
        return self.get_or_create_collection_id(collection_name)

    def upsert_document_embeddings(
        self,
        *,
        configuration_id: uuid.UUID,
        document_id: uuid.UUID,
        chunks: list[dict],
        embeddings: list[list[float]],
    ) -> int:
        """Wipe-and-rewrite of all vectors for a document.

        Uses a streaming generator + sliced sub-batches so peak memory is
        bounded by KB_VECTOR_INSERT_BATCH_SIZE records, not the full chunks list.
        """
        from app.core.config import settings  # noqa: PLC0415

        collection_id = self.resolve_collection_id_for_configuration(configuration_id)
        records_iter = _iter_chunk_records(
            document_id=document_id,
            collection_id=collection_id,
            chunks=chunks,
            embeddings=embeddings,
            chunk_index_offset=0,
        )
        batch_size = settings.KB_VECTOR_INSERT_BATCH_SIZE
        inserted = 0
        with self._pg_engine.begin() as conn:
            conn.execute(
                delete(VectorEmbedding).where(
                    _document_metadata_match(document_id)
                )
            )
            for sub_batch in _slice_iter(records_iter, batch_size):
                conn.execute(insert(VectorEmbedding), sub_batch)
                inserted += len(sub_batch)
        return inserted

    def insert_batch_embeddings(
        self,
        *,
        configuration_id: uuid.UUID,
        document_id: uuid.UUID,
        chunks: list[dict],
        embeddings: list[list[float]],
        chunk_index_offset: int = 0,
    ) -> int:
        """Insert a single batch of embeddings.

        Idempotent per-batch: first deletes any existing rows whose chunk_index
        falls inside this batch's range, then inserts fresh. Safe under retry.

        chunk_index_offset is the global index of the first chunk in `chunks` —
        the embed stage assigns these so that batches don't overlap.
        """
        from app.core.config import settings  # noqa: PLC0415

        # We must know the range to clear before inserting → use chunk count.
        # `chunks` is a small per-batch list (≤ KB_EMBED_BATCH_SIZE), so len() is cheap.
        chunk_count = len(chunks) if hasattr(chunks, "__len__") else None
        if chunk_count is None:
            # If caller passed a generator, materialise once for the range computation.
            # Per-batch chunks are bounded (~100) so this is fine.
            chunks = list(chunks)
            chunk_count = len(chunks)

        collection_id = self.resolve_collection_id_for_configuration(configuration_id)
        records_iter = _iter_chunk_records(
            document_id=document_id,
            collection_id=collection_id,
            chunks=chunks,
            embeddings=embeddings,
            chunk_index_offset=chunk_index_offset,
        )

        batch_size = settings.KB_VECTOR_INSERT_BATCH_SIZE
        batch_end_exclusive = chunk_index_offset + chunk_count
        inserted = 0
        with self._pg_engine.begin() as conn:
            # Idempotency: clear our own slice before re-inserting.
            conn.execute(
                delete(VectorEmbedding).where(
                    _document_metadata_match(document_id),
                    cast(
                        VectorEmbedding.cmetadata["chunk_index"].astext, Integer
                    ).between(chunk_index_offset, batch_end_exclusive - 1),
                )
            )
            for sub_batch in _slice_iter(records_iter, batch_size):
                conn.execute(insert(VectorEmbedding), sub_batch)
                inserted += len(sub_batch)
        return inserted

    def count_document_embeddings(self, document_id: uuid.UUID) -> int:
        """Count vector rows for a document — used by load_vector to verify completeness."""
        with self._pg_engine.begin() as conn:
            row = conn.execute(
                select(func.count())
                .select_from(VectorEmbedding)
                .where(
                    _document_metadata_match(document_id)
                )
            ).scalar_one()
            return int(row or 0)

    def get_existing_chunk_indices(self, document_id: uuid.UUID) -> set[int]:
        """Return the set of chunk_index values currently persisted for a document.

        Used by the reissue-missing-batches recovery path in the load_vector
        stage: compare against `range(0, expected_total)` to find the chunks
        whose embed batch exhausted retries (e.g. an extended provider outage).
        Each missing index is then re-dispatched as a fresh single-chunk batch.
        """
        with self._pg_engine.begin() as conn:
            result = conn.execute(
                select(
                    cast(VectorEmbedding.cmetadata["chunk_index"].astext, Integer)
                ).where(
                    _document_metadata_match(document_id)
                )
            )
            return {row[0] for row in result if row[0] is not None}

    def search(
        self,
        *,
        configuration_id: uuid.UUID,
        query_vector: list[float],
        max_docs: int,
        score_threshold: float,
        organization_id: uuid.UUID | str,
        metadata_filter: dict[str, Any] | None = None,
        metadata_filters: list[dict[str, Any]] | None = None,
    ) -> list[dict]:
        if max_docs <= 0:
            return []
        collection_id = self.resolve_collection_id_for_configuration(configuration_id)
        statement = _build_search_statement(
            collection_id=collection_id,
            query_vector=query_vector,
            max_docs=max_docs,
            score_threshold=score_threshold,
            organization_id=organization_id,
            metadata_filter=metadata_filter,
            metadata_filters=metadata_filters,
        )
        with self._pg_engine.begin() as conn:
            rows = conn.execute(statement).mappings().all()

        results: list[dict[str, Any]] = []
        for row in rows:
            mapped = _map_search_row(row)
            if mapped is not None:
                results.append(mapped)
        return results

    def lexical_search(
        self,
        *,
        configuration_id: uuid.UUID,
        query_text: str,
        max_docs: int,
        organization_id: uuid.UUID | str,
        metadata_filter: dict[str, Any] | None = None,
        metadata_filters: list[dict[str, Any]] | None = None,
    ) -> list[dict]:
        if max_docs <= 0:
            return []
        collection_id = self.resolve_collection_id_for_configuration(configuration_id)
        statement = _build_lexical_search_statement(
            collection_id=collection_id,
            query_text=query_text,
            max_docs=max_docs,
            organization_id=organization_id,
            metadata_filter=metadata_filter,
            metadata_filters=metadata_filters,
        )
        with self._pg_engine.begin() as conn:
            rows = conn.execute(statement).mappings().all()

        results: list[dict[str, Any]] = []
        for row in rows:
            mapped = _map_search_row(row)
            if mapped is not None:
                results.append(mapped)
        return results

    def hybrid_search(
        self,
        *,
        configuration_id: uuid.UUID,
        organization_id: uuid.UUID | str,
        query_vector: list[float],
        query_text: str,
        max_docs: int,
        final_limit: int,
        score_threshold: float,
        rrf_k: int,
        metadata_filter: dict[str, Any] | None = None,
        metadata_filters: list[dict[str, Any]] | None = None,
    ) -> list[dict]:
        semantic_results = self.search(
            configuration_id=configuration_id,
            organization_id=organization_id,
            query_vector=query_vector,
            max_docs=max_docs,
            score_threshold=score_threshold,
            metadata_filter=metadata_filter,
            metadata_filters=metadata_filters,
        )
        lexical_results = self.lexical_search(
            configuration_id=configuration_id,
            organization_id=organization_id,
            query_text=query_text,
            max_docs=max_docs,
            metadata_filter=metadata_filter,
            metadata_filters=metadata_filters,
        )
        return _merge_hybrid_candidates(
            semantic_results=semantic_results,
            lexical_results=lexical_results,
            max_docs=final_limit,
            rrf_k=rrf_k,
        )

    def delete_document_embeddings(self, document_id: uuid.UUID) -> int:
        """Delete all vector embeddings for a document. Returns row count."""
        with self._pg_engine.begin() as conn:
            result = conn.execute(
                delete(VectorEmbedding).where(
                    _document_metadata_match(document_id)
                )
            )
            return result.rowcount or 0


class AsyncVectorRepository:
    """Async counterpart to VectorRepository — for FastAPI routes via asyncpg / AsyncSession.

    Never touches the sync engine; all I/O goes through await session.execute().
    """

    def __init__(self, session: "AsyncSession") -> None:
        self._session = session

    async def get_or_create_collection_id(self, collection_name: str) -> uuid.UUID:
        statement = (
            pg_insert(VectorCollection)
            .values(name=collection_name, cmetadata={})
            .on_conflict_do_update(
                index_elements=[VectorCollection.name],
                set_={"name": collection_name},
            )
            .returning(VectorCollection.uuid)
        )
        result = await self._session.execute(statement)
        row = result.mappings().first()
        if not row:
            raise RuntimeError("Could not resolve vector collection id")
        return row["uuid"]

    async def resolve_collection_id_for_configuration(
        self, configuration_id: uuid.UUID
    ) -> uuid.UUID:
        result = await self._session.execute(
            select(Configuration.collection_name).where(
                Configuration.id == configuration_id
            )
        )
        row = result.mappings().first()
        if not row:
            raise LookupError(f"Configuration not found: {configuration_id}")
        return await self.get_or_create_collection_id(row["collection_name"])

    async def search(
        self,
        *,
        configuration_id: uuid.UUID,
        query_vector: list[float],
        max_docs: int,
        score_threshold: float,
        organization_id: uuid.UUID | str,
        metadata_filter: dict[str, Any] | None = None,
        metadata_filters: list[dict[str, Any]] | None = None,
    ) -> list[dict]:
        if max_docs <= 0:
            return []
        collection_id = await self.resolve_collection_id_for_configuration(
            configuration_id
        )
        statement = _build_search_statement(
            collection_id=collection_id,
            query_vector=query_vector,
            max_docs=max_docs,
            score_threshold=score_threshold,
            organization_id=organization_id,
            metadata_filter=metadata_filter,
            metadata_filters=metadata_filters,
        )
        result = await self._session.execute(statement)
        rows = result.mappings().all()
        mapped_rows: list[dict[str, Any]] = []
        for row in rows:
            mapped = _map_search_row(row)
            if mapped is not None:
                mapped_rows.append(mapped)
        return mapped_rows

    async def lexical_search(
        self,
        *,
        configuration_id: uuid.UUID,
        query_text: str,
        max_docs: int,
        organization_id: uuid.UUID | str,
        metadata_filter: dict[str, Any] | None = None,
        metadata_filters: list[dict[str, Any]] | None = None,
    ) -> list[dict]:
        if max_docs <= 0:
            return []
        collection_id = await self.resolve_collection_id_for_configuration(
            configuration_id
        )
        statement = _build_lexical_search_statement(
            collection_id=collection_id,
            query_text=query_text,
            max_docs=max_docs,
            organization_id=organization_id,
            metadata_filter=metadata_filter,
            metadata_filters=metadata_filters,
        )
        result = await self._session.execute(statement)
        rows = result.mappings().all()
        mapped_rows: list[dict[str, Any]] = []
        for row in rows:
            mapped = _map_search_row(row)
            if mapped is not None:
                mapped_rows.append(mapped)
        return mapped_rows

    async def hybrid_search(
        self,
        *,
        configuration_id: uuid.UUID,
        organization_id: uuid.UUID | str,
        query_vector: list[float],
        query_text: str,
        max_docs: int,
        final_limit: int,
        score_threshold: float,
        rrf_k: int,
        metadata_filter: dict[str, Any] | None = None,
        metadata_filters: list[dict[str, Any]] | None = None,
    ) -> list[dict]:
        semantic_results = await self.search(
            configuration_id=configuration_id,
            organization_id=organization_id,
            query_vector=query_vector,
            max_docs=max_docs,
            score_threshold=score_threshold,
            metadata_filter=metadata_filter,
            metadata_filters=metadata_filters,
        )
        lexical_results = await self.lexical_search(
            configuration_id=configuration_id,
            organization_id=organization_id,
            query_text=query_text,
            max_docs=max_docs,
            metadata_filter=metadata_filter,
            metadata_filters=metadata_filters,
        )
        return _merge_hybrid_candidates(
            semantic_results=semantic_results,
            lexical_results=lexical_results,
            max_docs=final_limit,
            rrf_k=rrf_k,
        )

    async def delete_document_embeddings(self, document_id: uuid.UUID) -> int:
        result = await self._session.execute(
            delete(VectorEmbedding).where(
                _document_metadata_match(document_id)
            )
        )
        await self._session.commit()
        return result.rowcount or 0
