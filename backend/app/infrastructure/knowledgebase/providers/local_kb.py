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
from uuid import UUID

import httpx
import structlog

from app.core.config import Settings
from app.core.exceptions import (
    KBAuthError,
    KBConfigError,
    KBConnectionError,
    KBTimeoutError,
    KBValidationError,
)
from app.infrastructure.knowledgebase.context import assemble_context
from app.infrastructure.knowledgebase.dedup import deduplicate_chunks
from app.infrastructure.knowledgebase.ranking import rank_retrieved_chunks
from app.schemas.knowledgebase import (
    KBDocumentIngestRequest,
    KBDocumentIngestResponse,
    KBDocumentStatusResponse,
    KnowledgebaseResult,
    RetrievedChunk,
)

from .base import BaseKnowledgebaseProvider

logger = structlog.get_logger(__name__)


class LocalKBProvider(BaseKnowledgebaseProvider):
    """KB provider backed by a local KB service container."""

    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self._client = httpx.AsyncClient(
            base_url=self.settings.KB_LOCAL_BASE_URL,
            timeout=httpx.Timeout(self.settings.KB_TIMEOUT),
            headers={"Authorization": f"Bearer {self.settings.KB_API_SECRET}"},
        )
        self._config_id: str | None = None

    @property
    def provider_name(self) -> str:
        return "local"

    async def search(
        self,
        query: str,
        organization_id: UUID | str,
        max_docs: int | None = None,
        score_threshold: float | None = None,
        metadata_filter: dict | None = None,
        configuration_id: str | None = None,
    ) -> KnowledgebaseResult:
        start = time.monotonic()
        resolved_max_docs = max_docs if max_docs is not None else self.settings.KB_MAX_DOCS
        resolved_score_threshold = (
            score_threshold
            if score_threshold is not None
            else self.settings.KB_SCORE_THRESHOLD
        )

        payload: dict[str, Any] = {
            "query": query,
            "organization_id": str(organization_id),
            "limit": resolved_max_docs,
            "score_threshold": resolved_score_threshold,
            "visibility_context": _visibility_context(metadata_filter),
        }

        data = await self._post("/api/kb/search", payload)

        raw_items = data.get("results", []) if isinstance(data, dict) else []
        chunks = [
            RetrievedChunk(
                text=item.get("text", ""),
                metadata=_chunk_metadata(item),
                similarity_score=item.get("score"),
            )
            for item in raw_items
        ]
        chunks = rank_retrieved_chunks(deduplicate_chunks(chunks))
        context = assemble_context(chunks, self.settings.KB_CONTEXT_MAX_TOKENS)
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

        data = await self._post(
            "/api/kb/configuration/resolve",
            {},
        )
        config_id = data.get("id") if isinstance(data, dict) else None
        if not config_id:
            raise KBConfigError(
                f"KB configuration '{self.settings.KB_CONFIG_NAME}' could not be resolved"
            )
        self._config_id = config_id
        return config_id

    async def close(self) -> None:
        await self._client.aclose()

    async def ingest_document(
        self,
        request: KBDocumentIngestRequest,
    ) -> KBDocumentIngestResponse:
        """Start ingestion through the KB-service semantic document route."""
        config_id = await self.resolve_configuration()
        payload = {
            "source_type": request.source_type,
            "organization_id": str(request.organization_id),
            "playbook_document_id": str(request.playbook_document_id),
            "configuration_id": config_id,
            "source_uri": request.source_uri,
            "filename": request.filename,
            "content_type": request.content_type,
            "size_bytes": request.size_bytes,
            "source_title": request.source_title,
            "source_date": request.source_date.isoformat() if request.source_date else None,
            "is_official": request.is_official,
            "priority": request.priority,
            "visibility_policy": request.visibility_policy,
            "metadata_tags": request.metadata_tags,
            "status_webhook_url": request.status_webhook_url
            or _default_status_webhook_url(self.settings),
        }
        data = await self._post("/api/kb/ingest/document", payload)
        return KBDocumentIngestResponse(
            kb_service_document_id=data["kb_service_document_id"],
            playbook_document_id=request.playbook_document_id,
            task_id=data.get("task_id"),
            status=data.get("status", "pending"),
        )

    async def get_document_status(self, document_id: str) -> KBDocumentStatusResponse:
        """Fetch document status through the KB-service semantic route."""
        data = await self._get(f"/api/kb/status/documents/{document_id}")
        return KBDocumentStatusResponse(
            document_id=data.get("kb_service_document_id"),
            task_id=data.get("task_id"),
            status=data.get("status"),
            error_message=data.get("error_message"),
            metadata={"stages": data.get("stages", [])},
        )

    async def retry_document(
        self,
        kb_service_document_id: str,
    ) -> KBDocumentIngestResponse:
        """Retry ingestion through the KB-service semantic route."""
        data = await self._post(f"/api/kb/documents/{kb_service_document_id}/retry", {})
        return KBDocumentIngestResponse(
            kb_service_document_id=data["kb_service_document_id"],
            playbook_document_id=data["playbook_document_id"],
            task_id=data.get("task_id"),
            status=data.get("status", "pending"),
        )

    async def delete_document(self, kb_service_document_id: str) -> None:
        """Delete a document through the KB-service semantic route."""
        await self._delete(f"/api/kb/documents/{kb_service_document_id}")

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

    async def _delete(self, path: str) -> Any:
        """DELETE and map transport/HTTP errors to KB exceptions."""
        try:
            response = await self._client.delete(path)
        except httpx.TimeoutException as exc:
            raise KBTimeoutError(f"KB request to {path} timed out") from exc
        except httpx.HTTPError as exc:
            raise KBConnectionError(f"KB request to {path} failed: {exc}") from exc

        if response.status_code == 204:
            return None
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


def _chunk_metadata(item: dict[str, Any]) -> dict[str, Any]:
    metadata = dict(item.get("metadata", {}) or {})
    for key in (
        "document_id",
        "kb_service_document_id",
        "chunk_id",
        "chunk_index",
        "score",
        "source_title",
        "source_date",
        "is_official",
        "priority",
        "visibility_policy",
        "metadata_tags",
        "content_type",
    ):
        if key in item and key not in metadata:
            metadata[key] = item[key]
    return metadata


def _visibility_context(metadata_filter: dict | None) -> dict[str, Any]:
    visibility_policy = (metadata_filter or {}).get("visibility_policy")
    if isinstance(visibility_policy, dict):
        return {"role": "athlete", "visibility_policy": visibility_policy}
    return {"role": "athlete"}


def _default_status_webhook_url(settings: Settings) -> str:
    return f"{settings.API_PUBLIC_URL.rstrip('/')}/api/v1/kb/webhook"
