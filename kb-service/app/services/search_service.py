"""Search service — semantic similarity via the pgvector cosine-distance index."""
from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING

import structlog
from sqlalchemy.ext.asyncio import AsyncSession

from app.repositories.configuration_repo import ConfigurationRepository
from app.repositories.vector_repo import AsyncVectorRepository
from app.schemas.search import SearchChunk, SearchRequest, SearchResponse

if TYPE_CHECKING:
    # Imported only for typing — the concrete provider (and its openai dependency)
    # is built by another agent and resolved at runtime via the DI factory.
    from app.infrastructure.embedders.base import BaseEmbedProvider

logger = structlog.get_logger(__name__)


class SearchService:
    def __init__(
        self,
        session: AsyncSession,
        config_repo: ConfigurationRepository,
        vector_repo: AsyncVectorRepository,
        embed_provider: "BaseEmbedProvider",
    ) -> None:
        self._config_repo = config_repo
        self._vector_repo = vector_repo
        self._embed_provider = embed_provider

    async def search(self, req: SearchRequest) -> SearchResponse:
        config = await self._config_repo.get(req.configuration_id)
        if not config:
            raise LookupError(f"Configuration {req.configuration_id} not found")

        logger.info(
            "kb_embed_search_request",
            query=req.query,
            organization_id=str(req.organization_id),
            configuration_id=str(req.configuration_id),
            configuration_name=config.name,
            max_docs=req.max_docs,
            score_threshold=req.score_threshold,
            metadata_filter=req.metadata_filter,
        )

        # embed() is a sync, network-bound call. Run it in a worker thread so we
        # do not block the FastAPI async event loop.
        vectors = await asyncio.to_thread(self._embed_provider.embed, [req.query])
        if not vectors:
            logger.info(
                "kb_embed_search_response",
                query=req.query,
                organization_id=str(req.organization_id),
                configuration_id=str(req.configuration_id),
                total=0,
                chunks=[],
            )
            return SearchResponse(chunks=[], query=req.query, total=0)
        query_vector = vectors[0]

        chunk_results = await self._vector_repo.search(
            configuration_id=req.configuration_id,
            organization_id=req.organization_id,
            query_vector=query_vector,
            max_docs=req.max_docs,
            score_threshold=req.score_threshold,
            metadata_filter=req.metadata_filter,
        )
        response_chunks = [SearchChunk(**chunk) for chunk in chunk_results]
        logger.info(
            "kb_embed_search_response",
            query=req.query,
            organization_id=str(req.organization_id),
            configuration_id=str(req.configuration_id),
            configuration_name=config.name,
            total=len(response_chunks),
            chunks=[
                {
                    "document_id": str(c.document_id),
                    "score": round(c.score, 4),
                    "text_preview": c.text[:200],
                }
                for c in response_chunks[:5]
            ],
        )
        return SearchResponse(
            chunks=response_chunks,
            query=req.query,
            total=len(response_chunks),
        )
