"""Search service — semantic similarity via the pgvector cosine-distance index."""
from __future__ import annotations

import asyncio
import hashlib
import uuid
from typing import TYPE_CHECKING

import structlog

from app.core.config import settings
from app.infrastructure.rerankers.base import RerankCandidate
from app.repositories.vector_repo import AsyncVectorRepository, dedupe_ranked_results
from app.schemas.search import SearchRequest, SearchResponse, SearchResult
from app.services.configuration_service import ConfigurationService

if TYPE_CHECKING:
    # Imported only for typing — the concrete provider (and its openai dependency)
    # is built by another agent and resolved at runtime via the DI factory.
    from app.infrastructure.embedders.base import BaseEmbedProvider
    from app.infrastructure.rerankers.base import BaseRerankProvider

logger = structlog.get_logger(__name__)

RANKING_STRATEGY_HYBRID = "hybrid"
RANKING_STRATEGY_HYBRID_RERANK = "hybrid_rerank"


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


def _query_log_metadata(query: str) -> dict[str, object]:
    normalized = query.strip().encode("utf-8")
    return {
        "query_length": len(query),
        "query_sha256": hashlib.sha256(normalized).hexdigest()[:16],
    }


def _annotate_semantic_results(results: list[dict]) -> list[dict]:
    annotated: list[dict] = []
    for result in results:
        item = dict(result)
        metadata = dict(item.get("metadata") or {})
        metadata.setdefault("ranking_strategy", "semantic")
        item["metadata"] = metadata
        annotated.append(item)
    return annotated


class SearchService:
    def __init__(
        self,
        configuration_service: ConfigurationService,
        vector_repo: AsyncVectorRepository,
        embed_provider: "BaseEmbedProvider",
        rerank_provider: "BaseRerankProvider | None" = None,
    ) -> None:
        self._config_service = configuration_service
        self._vector_repo = vector_repo
        self._embed_provider = embed_provider
        self._rerank_provider = rerank_provider

    async def search(self, req: SearchRequest) -> SearchResponse:
        config = await self._config_service.resolve()
        metadata_filters = _metadata_filters_from_search_request(req)

        logger.info(
            "kb_embed_search_request",
            **_query_log_metadata(req.query),
            organization_id=str(req.organization_id),
            configuration_id=str(config.id),
            configuration_name=config.name,
            limit=req.limit,
            score_threshold=req.score_threshold,
            visibility_context_keys=sorted(req.visibility_context.keys()),
            source_types=req.source_types,
            has_file_filter=bool(req.file_ids),
            search_strategy=settings.KB_SEARCH_STRATEGY,
        )

        # embed() is a sync, network-bound call. Run it in a worker thread so we
        # do not block the FastAPI async event loop.
        vectors = await asyncio.to_thread(self._embed_provider.embed, [req.query])
        if not vectors:
            logger.info(
                "kb_embed_search_response",
                **_query_log_metadata(req.query),
                organization_id=str(req.organization_id),
                configuration_id=str(config.id),
                total=0,
                results=[],
                search_strategy=settings.KB_SEARCH_STRATEGY,
            )
            return SearchResponse(results=[], query=req.query, total=0)
        query_vector = vectors[0]

        chunk_results = await self._search_chunks(
            configuration_id=config.id,
            organization_id=req.organization_id,
            query=req.query,
            query_vector=query_vector,
            limit=req.limit,
            score_threshold=req.score_threshold,
            metadata_filters=metadata_filters,
        )
        response_results = [SearchResult(**chunk) for chunk in chunk_results]
        logger.info(
            "kb_embed_search_response",
            **_query_log_metadata(req.query),
            organization_id=str(req.organization_id),
            configuration_id=str(config.id),
            configuration_name=config.name,
            total=len(response_results),
            search_strategy=settings.KB_SEARCH_STRATEGY,
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

    async def _search_chunks(
        self,
        *,
        configuration_id: uuid.UUID,
        organization_id: uuid.UUID,
        query: str,
        query_vector: list[float],
        limit: int,
        score_threshold: float,
        metadata_filters: list[dict[str, object]],
    ) -> list[dict]:
        if settings.KB_SEARCH_STRATEGY != "hybrid":
            semantic_results = await self._vector_repo.search(
                configuration_id=configuration_id,
                organization_id=organization_id,
                query_vector=query_vector,
                max_docs=limit,
                score_threshold=score_threshold,
                metadata_filters=metadata_filters,
            )
            semantic_results = dedupe_ranked_results(semantic_results, max_docs=limit)
            return _annotate_semantic_results(semantic_results)

        should_rerank = self._should_rerank()
        final_limit = settings.KB_RERANK_CANDIDATE_LIMIT if should_rerank else limit
        try:
            hybrid_results = await self._vector_repo.hybrid_search(
                configuration_id=configuration_id,
                organization_id=organization_id,
                query_vector=query_vector,
                query_text=query,
                max_docs=settings.KB_HYBRID_CANDIDATE_LIMIT,
                final_limit=final_limit,
                score_threshold=score_threshold,
                rrf_k=settings.KB_RRF_K,
                metadata_filters=metadata_filters,
            )
        except Exception as exc:
            logger.warning(
                "kb_hybrid_search_failed_fallback_semantic",
                **_query_log_metadata(query),
                organization_id=str(organization_id),
                configuration_id=str(configuration_id),
                candidate_limit=settings.KB_HYBRID_CANDIDATE_LIMIT,
                final_limit=limit,
                failure_class=type(exc).__name__,
                exc_info=True,
            )
            semantic_results = await self._vector_repo.search(
                configuration_id=configuration_id,
                organization_id=organization_id,
                query_vector=query_vector,
                max_docs=limit,
                score_threshold=score_threshold,
                metadata_filters=metadata_filters,
            )
            semantic_results = dedupe_ranked_results(semantic_results, max_docs=limit)
            return _annotate_semantic_results(semantic_results)

        hybrid_results = dedupe_ranked_results(hybrid_results, max_docs=final_limit)
        if should_rerank:
            return await self._rerank_hybrid_results(
                query=query,
                hybrid_results=hybrid_results,
                limit=limit,
                organization_id=organization_id,
                configuration_id=configuration_id,
            )
        return hybrid_results[:limit]

    def _should_rerank(self) -> bool:
        return bool(settings.KB_RERANK_ENABLED and self._rerank_provider is not None)

    async def _rerank_hybrid_results(
        self,
        *,
        query: str,
        hybrid_results: list[dict],
        limit: int,
        organization_id: uuid.UUID,
        configuration_id: uuid.UUID,
    ) -> list[dict]:
        if not hybrid_results or self._rerank_provider is None:
            return hybrid_results[:limit]

        candidates = [
            RerankCandidate(
                original_index=index,
                chunk_id=result.get("chunk_id"),
                text=str(result.get("text") or ""),
            )
            for index, result in enumerate(hybrid_results)
        ]
        logger.info(
            "kb_hybrid_rerank_started",
            **_query_log_metadata(query),
            organization_id=str(organization_id),
            configuration_id=str(configuration_id),
            provider=self._rerank_provider.provider_name,
            candidate_count=len(candidates),
            top_n=limit,
        )
        reranked_results = await asyncio.to_thread(
            self._rerank_provider.rerank,
            query=query,
            candidates=candidates,
            top_n=limit,
        )

        final_results: list[dict] = []
        for reranked in reranked_results[:limit]:
            original_index = reranked.candidate.original_index
            if original_index < 0 or original_index >= len(hybrid_results):
                continue
            item = dict(hybrid_results[original_index])
            metadata = dict(item.get("metadata") or {})
            metadata["rerank_score"] = reranked.rerank_score
            if reranked.rerank_score is not None:
                item["score"] = reranked.rerank_score
                metadata["ranking_strategy"] = RANKING_STRATEGY_HYBRID_RERANK
            else:
                item["score"] = float(metadata.get("hybrid_score") or item.get("score") or 0.0)
                metadata["ranking_strategy"] = RANKING_STRATEGY_HYBRID
            item["metadata"] = metadata
            final_results.append(item)

        logger.info(
            "kb_hybrid_rerank_completed",
            **_query_log_metadata(query),
            organization_id=str(organization_id),
            configuration_id=str(configuration_id),
            provider=self._rerank_provider.provider_name,
            candidate_count=len(candidates),
            result_count=len(final_results),
            top_n=limit,
            used_rerank_scores=any(
                result.get("metadata", {}).get("rerank_score") is not None
                for result in final_results
            ),
        )
        return final_results
