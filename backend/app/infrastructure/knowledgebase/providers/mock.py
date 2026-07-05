"""Mock knowledgebase provider for local development and testing.

Returns pre-canned search results and a static configuration ID. No network
calls are made. Optionally reads fixtures from
backend/tests/fixtures/knowledgebase/mock_search_responses.json when present.
"""
from __future__ import annotations

import json
import time
from pathlib import Path
from uuid import UUID, uuid4

from app.core.config import Settings
from app.infrastructure.knowledgebase.context import assemble_context
from app.infrastructure.knowledgebase.ranking import rank_retrieved_chunks
from app.schemas.knowledgebase import (
    KBConversationFileIngestRequest,
    KBDocumentIngestRequest,
    KBDocumentIngestResponse,
    KBDocumentMetadataRefreshRequest,
    KBDocumentMetadataRefreshResponse,
    KBDocumentStatusResponse,
    KBIngestRequest,
    KnowledgebaseResult,
    RetrievedChunk,
)

from .base import BaseKnowledgebaseProvider

_FIXTURE_DIR = Path(__file__).parents[4] / "tests" / "fixtures" / "knowledgebase"
_MOCK_CONFIG_ID = "mock-config-id-abc123"

# Fallback fixture used when no fixture file is present, so the provider is
# useful out of the box.
_DEFAULT_ITEMS = [
    {
        "text": "Example knowledge base passage returned by the mock provider.",
        "metadata": {"doc_title": "Mock Source", "section_path": "Overview"},
        "similarity_score": 0.92,
    }
]


def _load_default_items() -> list[dict]:
    path = _FIXTURE_DIR / "mock_search_responses.json"
    if path.exists():
        fixture = json.loads(path.read_text(encoding="utf-8"))
        return fixture.get("default", {}).get("result", _DEFAULT_ITEMS)
    return _DEFAULT_ITEMS


class MockProvider(BaseKnowledgebaseProvider):
    """Fixture-based provider for offline development and unit tests."""

    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    @property
    def provider_name(self) -> str:
        return "mock"

    async def search(
        self,
        query: str,
        organization_id: UUID | str,
        max_docs: int | None = None,
        score_threshold: float | None = None,
        metadata_filter: dict | None = None,
        configuration_id: str | None = None,
    ) -> KnowledgebaseResult:
        return await self.search_admin_uploads(
            query=query,
            organization_id=organization_id,
            max_docs=max_docs,
            score_threshold=score_threshold,
            metadata_filter=metadata_filter,
            configuration_id=configuration_id,
        )

    async def search_admin_uploads(
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

        raw_items = _load_default_items()
        chunks = [
            RetrievedChunk(
                text=item["text"],
                metadata=item.get("metadata", {}),
                similarity_score=item.get("similarity_score"),
            )
            for item in raw_items[:resolved_max_docs]
            if (item.get("similarity_score") or 0) >= resolved_score_threshold
        ]

        chunks = rank_retrieved_chunks(chunks)
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

    async def search_conversation_files(
        self,
        query: str,
        organization_id: UUID | str,
        conversation_id: UUID | str,
        file_ids: list[UUID | str] | None = None,
        max_docs: int | None = None,
        score_threshold: float | None = None,
        configuration_id: str | None = None,
    ) -> KnowledgebaseResult:
        start = time.monotonic()
        latency_ms = int((time.monotonic() - start) * 1000)
        return KnowledgebaseResult(
            query=query,
            context="",
            sources=[],
            confidence=None,
            zero_hit=True,
            latency_ms=latency_ms,
        )

    async def health_check(self) -> bool:
        return True

    async def resolve_configuration(self) -> str:
        return _MOCK_CONFIG_ID

    async def ingest_document(
        self,
        request: KBDocumentIngestRequest,
    ) -> KBDocumentIngestResponse:
        return await self.ingest_source(request)

    async def ingest_source(
        self,
        request: KBIngestRequest,
    ) -> KBDocumentIngestResponse:
        if isinstance(request, KBDocumentIngestRequest):
            external_id = request.playbook_document_id
            task_id = f"mock-task-{request.playbook_document_id}"
            return KBDocumentIngestResponse(
                kb_service_document_id=external_id or uuid4(),
                source_type=request.source_type,
                playbook_document_id=request.playbook_document_id,
                task_id=task_id,
                status="pending",
            )

        if isinstance(request, KBConversationFileIngestRequest):
            return KBDocumentIngestResponse(
                kb_service_document_id=uuid4(),
                source_type=request.source_type,
                conversation_id=request.conversation_id,
                conversation_file_id=request.conversation_file_id,
                task_id=f"mock-task-{request.conversation_file_id}",
                status="pending",
            )

        return KBDocumentIngestResponse(
            kb_service_document_id=uuid4(),
            source_type=request.source_type,
            task_id="mock-task",
            status="pending",
        )

    async def get_document_status(self, document_id: str) -> KBDocumentStatusResponse:
        try:
            resolved_document_id = UUID(str(document_id))
        except ValueError:
            resolved_document_id = None
        return KBDocumentStatusResponse(
            document_id=resolved_document_id,
            status="SUCCESS",
        )

    async def retry_document(
        self,
        kb_service_document_id: str,
    ) -> KBDocumentIngestResponse:
        return KBDocumentIngestResponse(
            kb_service_document_id=uuid4(),
            source_type="admin_upload",
            playbook_document_id=uuid4(),
            task_id=f"mock-retry-{kb_service_document_id}",
            status="pending",
        )

    async def refresh_document_metadata(
        self,
        kb_service_document_id: str,
        request: KBDocumentMetadataRefreshRequest,
    ) -> KBDocumentMetadataRefreshResponse:
        return KBDocumentMetadataRefreshResponse(
            kb_service_document_id=UUID(kb_service_document_id),
            source_type="admin_upload",
            updated_embedding_count=0,
            metadata=request.metadata_tags,
        )

    async def delete_document(self, kb_service_document_id: str) -> None:
        return None
