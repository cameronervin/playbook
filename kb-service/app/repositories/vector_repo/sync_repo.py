"""Sync vector repository used by KB-service worker tasks."""
from __future__ import annotations

import uuid
from typing import TYPE_CHECKING, Any

from sqlalchemy import Integer, cast, delete, func, insert, select
from sqlalchemy.dialects.postgresql import insert as pg_insert

from app.models.configuration import Configuration
from app.models.vector_collection import VectorCollection
from app.models.vector_embedding import VectorEmbedding
from app.repositories.vector_repo.mapping import _map_search_row
from app.repositories.vector_repo.queries import (
    _build_lexical_search_statement,
    _build_search_statement,
    _document_metadata_match,
)
from app.repositories.vector_repo.ranking import (
    _dedupe_fetch_limit,
    _merge_hybrid_candidates,
    dedupe_ranked_results,
)
from app.repositories.vector_repo.records import _iter_chunk_records

if TYPE_CHECKING:
    from sqlalchemy.engine import Engine


def _slice_iter(iterator, batch_size: int):
    """Yield successive lists of up to batch_size elements."""
    batch: list = []
    for item in iterator:
        batch.append(item)
        if len(batch) >= batch_size:
            yield batch
            batch = []
    if batch:
        yield batch


class VectorRepository:
    """Sync vector persistence + search used by Celery worker tasks."""

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

    def resolve_collection_id_for_configuration(
        self, configuration_id: uuid.UUID
    ) -> uuid.UUID:
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
        """Wipe and rewrite all vectors for a document."""
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
                delete(VectorEmbedding).where(_document_metadata_match(document_id))
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
        """Insert one idempotent batch of embeddings."""
        from app.core.config import settings  # noqa: PLC0415

        chunk_count = len(chunks) if hasattr(chunks, "__len__") else None
        if chunk_count is None:
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
        """Count vector rows for a document."""
        with self._pg_engine.begin() as conn:
            row = conn.execute(
                select(func.count())
                .select_from(VectorEmbedding)
                .where(_document_metadata_match(document_id))
            ).scalar_one()
            return int(row or 0)

    def get_existing_chunk_indices(self, document_id: uuid.UUID) -> set[int]:
        """Return existing chunk_index values for a document."""
        with self._pg_engine.begin() as conn:
            result = conn.execute(
                select(
                    cast(VectorEmbedding.cmetadata["chunk_index"].astext, Integer)
                ).where(_document_metadata_match(document_id))
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
            max_docs=_dedupe_fetch_limit(max_docs),
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
        return dedupe_ranked_results(results, max_docs=max_docs)

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
            max_docs=_dedupe_fetch_limit(max_docs),
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
        return dedupe_ranked_results(results, max_docs=max_docs)

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
                delete(VectorEmbedding).where(_document_metadata_match(document_id))
            )
            return result.rowcount or 0
