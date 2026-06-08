"""Abstract base class for knowledgebase providers.

All provider implementations subclass BaseKnowledgebaseProvider and implement
the abstract retrieval/health/config methods. The default ``close()`` is a
no-op so lightweight providers (e.g. MockProvider) don't need to override it.

NOTE: ingestion / pipeline-provisioning methods are intentionally NOT abstract
here — see ``STUBS.md`` ("Phase B"). That keeps the Mock and Local providers
simple and focused on retrieval.
"""
from __future__ import annotations

from abc import ABC, abstractmethod

import structlog

from app.core.config import settings
from app.schemas.knowledgebase import (
    KBDocumentIngestRequest,
    KBDocumentIngestResponse,
    KBDocumentStatusResponse,
    KnowledgebaseResult,
)

logger = structlog.get_logger(__name__)


class BaseKnowledgebaseProvider(ABC):
    """Abstract base class for knowledgebase providers.

    Abstracts retrieval, configuration resolution, and health checking.
    Ingestion methods (see STUBS.md "Phase B") are added per-provider when an
    ingestion backend is implemented.
    """

    @property
    @abstractmethod
    def provider_name(self) -> str:
        """Human-readable provider name for logging and diagnostics."""
        ...

    @abstractmethod
    async def search(
        self,
        query: str,
        max_docs: int = settings.KB_MAX_DOCS,
        score_threshold: float = settings.KB_SCORE_THRESHOLD,
        metadata_filter: dict | None = None,
        configuration_id: str | None = None,
    ) -> KnowledgebaseResult:
        """Perform a semantic similarity search against the knowledge base.

        Args:
            query: Natural language query string.
            max_docs: Maximum number of chunks to return.
            score_threshold: Minimum similarity score; results below are excluded.
            metadata_filter: Optional metadata filter dict.
            configuration_id: Target pipeline/collection ID, or None for default.

        Returns:
            KnowledgebaseResult with assembled context, sources, and latency.
        """
        ...

    @abstractmethod
    async def health_check(self) -> bool:
        """Check whether the underlying provider is reachable.

        Returns:
            True if healthy, False if degraded or unavailable.
        """
        ...

    @abstractmethod
    async def resolve_configuration(self) -> str:
        """Resolve the pipeline configuration name to its ID.

        Resolution should be cached after the first successful call.
        Implementations raise KBConfigError when the configuration cannot be
        found, triggering a fail-fast at startup.

        Returns:
            The configuration ID string.
        """
        ...

    async def close(self) -> None:
        """Release provider resources (e.g. HTTP connection pool).

        Default implementation is a no-op. Providers that hold open connections
        (e.g. an httpx.AsyncClient) must override this and call it on shutdown.
        """
        logger.debug("knowledgebase_provider_close_noop", provider=self.provider_name)

    async def ingest_document(
        self,
        request: KBDocumentIngestRequest,
    ) -> KBDocumentIngestResponse:
        """Start ingestion for an admin-uploaded document."""
        raise NotImplementedError

    async def get_document_status(self, task_id: str) -> KBDocumentStatusResponse:
        """Return KB-service ingestion status for a task/document."""
        raise NotImplementedError

    async def delete_document(self, kb_service_document_id: str) -> None:
        """Delete/archive a document from the KB service."""
        raise NotImplementedError
