"""Async vector repository used by KB-service API services."""
from __future__ import annotations

import uuid
from typing import TYPE_CHECKING, Any

from sqlalchemy import delete, select
from sqlalchemy.dialects.postgresql import insert as pg_insert

from app.models.configuration import Configuration
from app.models.vector_collection import VectorCollection
from app.models.vector_embedding import VectorEmbedding
from app.repositories.vector_mapping import _map_search_row
from app.repositories.vector_queries import (
    _build_lexical_search_statement,
    _build_search_statement,
    _document_metadata_match,
)
from app.repositories.vector_ranking import (
    _dedupe_fetch_limit,
    _merge_hybrid_candidates,
    dedupe_ranked_results,
)

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession


class AsyncVectorRepository:
    """Async vector persistence + search used by FastAPI services."""

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
            max_docs=_dedupe_fetch_limit(max_docs),
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
        return dedupe_ranked_results(mapped_rows, max_docs=max_docs)

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
            max_docs=_dedupe_fetch_limit(max_docs),
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
        return dedupe_ranked_results(mapped_rows, max_docs=max_docs)

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
            delete(VectorEmbedding).where(_document_metadata_match(document_id))
        )
        await self._session.commit()
        return result.rowcount or 0
