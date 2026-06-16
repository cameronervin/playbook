"""Search service — semantic similarity via the pgvector cosine-distance index."""
from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING

import structlog

from app.repositories.vector_repo import AsyncVectorRepository
from app.schemas.search import SearchRequest, SearchResponse, SearchResult
from app.services.configuration_service import ConfigurationService

if TYPE_CHECKING:
    # Imported only for typing — the concrete provider (and its openai dependency)
    # is built by another agent and resolved at runtime via the DI factory.
    from app.infrastructure.embedders.base import BaseEmbedProvider

logger = structlog.get_logger(__name__)


def _metadata_filter_from_visibility_context(
    visibility_context: dict,
) -> dict[str, object]:
    visibility_policy = visibility_context.get("visibility_policy")
    if isinstance(visibility_policy, dict):
        return {"visibility_policy": visibility_policy}
    if visibility_context.get("role") == "athlete":
        return {"visibility_policy": {"scope": "all_athletes"}}
    return {"visibility_policy": {"scope": "all_athletes"}}


def _metadata_filters_from_search_request(req: SearchRequest) -> list[dict[str, object]]:
    filters: list[dict[str, object]] = []

    if "admin_upload" in req.source_types:
        filters.append(
            {
                "source_type": "admin_upload",
                **_metadata_filter_from_visibility_context(req.visibility_context),
            }
        )

    if "conversation_file" in req.source_types:
        if req.conversation_id is None:
            return filters
        private_filter: dict[str, object] = {
            "source_type": "conversation_file",
            "conversation_id": str(req.conversation_id),
            "visibility_policy": {"scope": "conversation"},
        }
        if req.file_ids:
            filters.extend(
                {
                    **private_filter,
                    "conversation_file_id": str(file_id),
                }
                for file_id in req.file_ids
            )
        else:
            filters.append(private_filter)

    return filters


class SearchService:
    def __init__(
        self,
        configuration_service: ConfigurationService,
        vector_repo: AsyncVectorRepository,
        embed_provider: "BaseEmbedProvider",
    ) -> None:
        self._config_service = configuration_service
        self._vector_repo = vector_repo
        self._embed_provider = embed_provider

    async def search(self, req: SearchRequest) -> SearchResponse:
        config = await self._config_service.resolve()
        metadata_filters = _metadata_filters_from_search_request(req)

        logger.info(
            "kb_embed_search_request",
            query=req.query,
            organization_id=str(req.organization_id),
            configuration_id=str(config.id),
            configuration_name=config.name,
            limit=req.limit,
            score_threshold=req.score_threshold,
            visibility_context=req.visibility_context,
            source_types=req.source_types,
            has_file_filter=bool(req.file_ids),
        )

        # embed() is a sync, network-bound call. Run it in a worker thread so we
        # do not block the FastAPI async event loop.
        vectors = await asyncio.to_thread(self._embed_provider.embed, [req.query])
        if not vectors:
            logger.info(
                "kb_embed_search_response",
                query=req.query,
                organization_id=str(req.organization_id),
                configuration_id=str(config.id),
                total=0,
                results=[],
            )
            return SearchResponse(results=[], query=req.query, total=0)
        query_vector = vectors[0]

        chunk_results = await self._vector_repo.search(
            configuration_id=config.id,
            organization_id=req.organization_id,
            query_vector=query_vector,
            max_docs=req.limit,
            score_threshold=req.score_threshold,
            metadata_filters=metadata_filters,
        )
        response_results = [SearchResult(**chunk) for chunk in chunk_results]
        logger.info(
            "kb_embed_search_response",
            query=req.query,
            organization_id=str(req.organization_id),
            configuration_id=str(config.id),
            configuration_name=config.name,
            total=len(response_results),
            results=[
                {
                    "document_id": str(c.document_id),
                    "chunk_id": str(c.chunk_id) if c.chunk_id else None,
                    "source_type": c.metadata.get("source_type"),
                    "score": round(c.score, 4),
                }
                for c in response_results[:5]
            ],
        )
        return SearchResponse(
            results=response_results,
            query=req.query,
            total=len(response_results),
        )
