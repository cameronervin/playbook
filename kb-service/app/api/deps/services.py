"""API dependency providers for service wiring (Dependency Injection)."""
from __future__ import annotations

from typing import TYPE_CHECKING, cast

from fastapi import Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.infrastructure.db.session import get_db
from app.repositories.vector_repo import AsyncVectorRepository
from app.services.configuration_service import ConfigurationService
from app.services.ingestion import IngestionService
from app.services.search_service import SearchService

if TYPE_CHECKING:
    # Typed-only import — the concrete provider (with its openai dependency) is
    # resolved lazily at runtime via the factory below.
    from app.infrastructure.embedders.base import BaseEmbedProvider
    from app.infrastructure.rerankers.base import BaseRerankProvider


def get_embed_provider_dependency(request: Request) -> "BaseEmbedProvider":
    """Return the process-wide embed provider, caching it on app.state.

    The factory import is lazy so importing this module never drags in openai.
    """
    provider = getattr(request.app.state, "embed_provider", None)
    if provider is None:
        from app.infrastructure.embedders.factory import get_embed_provider  # noqa: I001, PLC0415

        request.app.state.embed_provider = get_embed_provider()
        provider = request.app.state.embed_provider
    return cast("BaseEmbedProvider", provider)


def get_rerank_provider_dependency(request: Request) -> "BaseRerankProvider | None":
    """Return the process-wide reranker provider only when search can use it."""
    if not settings.KB_RERANK_ENABLED or settings.KB_SEARCH_STRATEGY != "hybrid":
        return None

    provider = getattr(request.app.state, "rerank_provider", None)
    if provider is None:
        from app.infrastructure.rerankers.factory import get_rerank_provider  # noqa: I001, PLC0415

        request.app.state.rerank_provider = get_rerank_provider()
        provider = request.app.state.rerank_provider
    return cast("BaseRerankProvider", provider)


def get_search_service(
    db: AsyncSession = Depends(get_db),
    embed_provider: "BaseEmbedProvider" = Depends(get_embed_provider_dependency),
    rerank_provider: "BaseRerankProvider | None" = Depends(
        get_rerank_provider_dependency
    ),
) -> SearchService:
    return SearchService(
        configuration_service=ConfigurationService(db),
        vector_repo=AsyncVectorRepository(db),
        embed_provider=embed_provider,
        rerank_provider=rerank_provider,
    )


def get_ingestion_service(db: AsyncSession = Depends(get_db)) -> IngestionService:
    return IngestionService(db)


def get_configuration_service(db: AsyncSession = Depends(get_db)) -> ConfigurationService:
    return ConfigurationService(db)
