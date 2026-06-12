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
from app.schemas.knowledgebase import (
    KBDocumentIngestRequest,
    KBDocumentIngestResponse,
    KBDocumentStatusResponse,
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
        return True

    async def resolve_configuration(self) -> str:
        return _MOCK_CONFIG_ID

    async def ingest_document(
        self,
        request: KBDocumentIngestRequest,
    ) -> KBDocumentIngestResponse:
        return KBDocumentIngestResponse(
            kb_service_document_id=request.playbook_document_id or uuid4(),
            playbook_document_id=request.playbook_document_id,
            task_id=f"mock-task-{request.playbook_document_id}",
            status="pending",
        )

    async def get_document_status(self, task_id: str) -> KBDocumentStatusResponse:
        return KBDocumentStatusResponse(task_id=task_id, status="SUCCESS")

    async def delete_document(self, kb_service_document_id: str) -> None:
        return None
