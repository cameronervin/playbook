"""Local KB service provider.

Talks to a self-hosted KB service over HTTP (settings.KB_LOCAL_BASE_URL) using
Bearer-token auth. Retrieval results are deduplicated and assembled into a
context string via the shared context/dedup helpers.

This is a retrieval-focused provider — ingestion / pipeline provisioning lives
in "Phase B" (see STUBS.md). Create one instance for the app lifetime and call
``close()`` on shutdown to release the httpx connection pool.
"""
from __future__ import annotations

import time
from typing import Any

import httpx
import structlog

from app.core.config import settings
from app.core.exceptions import (
    KBAuthError,
    KBConfigError,
    KBConnectionError,
    KBTimeoutError,
    KBValidationError,
)
from app.infrastructure.knowledgebase.context import assemble_context
from app.infrastructure.knowledgebase.dedup import deduplicate_chunks
from app.schemas.knowledgebase import KnowledgebaseResult, RetrievedChunk

from .base import BaseKnowledgebaseProvider

logger = structlog.get_logger(__name__)


class LocalKBProvider(BaseKnowledgebaseProvider):
    """KB provider backed by a local KB service container."""

    def __init__(self) -> None:
        self._client = httpx.AsyncClient(
            base_url=settings.KB_LOCAL_BASE_URL,
            timeout=httpx.Timeout(settings.KB_TIMEOUT),
            headers={"Authorization": f"Bearer {settings.KB_API_SECRET}"},
        )
        self._config_id: str | None = None

    @property
    def provider_name(self) -> str:
        return "local"

    async def search(
        self,
        query: str,
        max_docs: int = settings.KB_MAX_DOCS,
        score_threshold: float = settings.KB_SCORE_THRESHOLD,
        metadata_filter: dict | None = None,
        configuration_id: str | None = None,
    ) -> KnowledgebaseResult:
        start = time.monotonic()
        config_id = configuration_id or await self.resolve_configuration()

        payload: dict[str, Any] = {
            "query": query,
            "max_docs": max_docs,
            "score_threshold": score_threshold,
            "configuration_id": config_id,
        }
        if metadata_filter:
            payload["metadata_filter"] = metadata_filter

        # Matches the kb-service contract: POST /api/kb/embed/search returns
        # {"chunks": [{document_id, text, score, metadata}], "query", "total"}.
        data = await self._post("/api/kb/embed/search", payload)

        raw_items = data.get("chunks", []) if isinstance(data, dict) else []
        chunks = [
            RetrievedChunk(
                text=item.get("text", ""),
                metadata=item.get("metadata", {}),
                similarity_score=item.get("score"),
            )
            for item in raw_items
        ]
        chunks = deduplicate_chunks(chunks)
        context = assemble_context(chunks, settings.KB_CONTEXT_MAX_TOKENS)
        latency_ms = int((time.monotonic() - start) * 1000)

        return KnowledgebaseResult(
            query=query,
            context=context,
            sources=chunks,
            confidence=chunks[0].similarity_score if chunks else None,
            zero_hit=len(chunks) == 0,
            latency_ms=latency_ms,
        )

    async def health_check(self) -> bool:
        try:
            response = await self._client.get("/health")
        except httpx.HTTPError as exc:
            logger.warning("kb_local_health_check_failed", error=str(exc))
            return False
        else:
            return response.status_code == 200

    async def resolve_configuration(self) -> str:
        if self._config_id is not None:
            return self._config_id

        # The kb-service has no dedicated resolve endpoint; configurations are
        # looked up by name via the list route (GET /api/kb/configuration/?name=).
        data = await self._get(
            "/api/kb/configuration/", params={"name": settings.KB_CONFIG_NAME}
        )
        rows = data if isinstance(data, list) else []
        config_id = rows[0].get("id") if rows else None
        if not config_id:
            raise KBConfigError(
                f"KB configuration '{settings.KB_CONFIG_NAME}' could not be resolved"
            )
        self._config_id = config_id
        return config_id

    async def close(self) -> None:
        await self._client.aclose()

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    async def _post(self, path: str, json_body: dict[str, Any]) -> Any:
        """POST JSON and map transport/HTTP errors to KB exceptions."""
        try:
            response = await self._client.post(path, json=json_body)
        except httpx.TimeoutException as exc:
            raise KBTimeoutError(f"KB request to {path} timed out") from exc
        except httpx.HTTPError as exc:
            raise KBConnectionError(f"KB request to {path} failed: {exc}") from exc

        return self._handle_response(path, response)

    async def _get(self, path: str, params: dict[str, Any] | None = None) -> Any:
        """GET and map transport/HTTP errors to KB exceptions."""
        try:
            response = await self._client.get(path, params=params)
        except httpx.TimeoutException as exc:
            raise KBTimeoutError(f"KB request to {path} timed out") from exc
        except httpx.HTTPError as exc:
            raise KBConnectionError(f"KB request to {path} failed: {exc}") from exc

        return self._handle_response(path, response)

    @staticmethod
    def _handle_response(path: str, response: httpx.Response) -> Any:
        """Map HTTP status codes to KB exceptions, else return parsed JSON."""
        if response.status_code in (401, 403):
            raise KBAuthError(f"KB auth failed ({response.status_code}) for {path}")
        if response.status_code == 422:
            raise KBValidationError(f"KB rejected request to {path} (422)")
        if response.status_code >= 500:
            raise KBConnectionError(f"KB server error ({response.status_code}) for {path}")

        return response.json()
