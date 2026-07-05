from __future__ import annotations

from datetime import date
from uuid import uuid4

import pytest

from app.infrastructure.knowledgebase.providers.local_kb import LocalKBProvider
from app.schemas.knowledgebase import (
    KBConversationFileIngestRequest,
    KBDocumentIngestRequest,
    KBDocumentMetadataRefreshRequest,
)


class _RecordingLocalKBProvider(LocalKBProvider):
    def __init__(self, settings) -> None:
        super().__init__(settings)
        self.posts: list[tuple[str, dict]] = []
        self.patches: list[tuple[str, dict]] = []

    async def resolve_configuration(self) -> str:
        return "config-123"

    async def _post(self, path: str, json_body: dict) -> dict:
        self.posts.append((path, json_body))
        response = {
            "kb_service_document_id": str(uuid4()),
            "source_type": json_body["source_type"],
            "task_id": "task-1",
            "status": "pending",
        }
        if json_body["source_type"] == "admin_upload":
            response["playbook_document_id"] = json_body["playbook_document_id"]
        else:
            response["conversation_id"] = json_body["conversation_id"]
            response["conversation_file_id"] = json_body["conversation_file_id"]
        return response

    async def _patch(self, path: str, json_body: dict) -> dict:
        self.patches.append((path, json_body))
        return {
            "kb_service_document_id": path.removesuffix("/metadata").rsplit("/", 1)[
                -1
            ],
            "source_type": "admin_upload",
            "playbook_document_id": str(uuid4()),
            "updated_embedding_count": 3,
            "metadata": json_body,
        }


class _SearchRecordingLocalKBProvider(LocalKBProvider):
    def __init__(self, settings, payload: dict) -> None:
        super().__init__(settings)
        self.payload = payload
        self.posts: list[tuple[str, dict]] = []

    async def _post(self, path: str, json_body: dict) -> dict:
        self.posts.append((path, json_body))
        return self.payload


@pytest.mark.asyncio
async def test_local_kb_provider_sends_default_backend_webhook_url(test_settings) -> None:
    settings = test_settings.model_copy(
        update={
            "API_PUBLIC_URL": "http://backend.test",
            "KB_LOCAL_BASE_URL": "http://kb.test",
            "KB_API_SECRET": "test-kb-secret",
        }
    )
    provider = _RecordingLocalKBProvider(settings)
    request = KBDocumentIngestRequest(
        organization_id=uuid4(),
        playbook_document_id=uuid4(),
        source_uri="http://storage.test/document.pdf",
        filename="document.pdf",
        content_type="application/pdf",
        size_bytes=123,
        source_title="Document",
    )

    await provider.ingest_document(request)

    assert provider.posts[0][1]["status_webhook_url"] == (
        "http://backend.test/api/v1/kb/webhook"
    )


@pytest.mark.asyncio
async def test_local_kb_provider_preserves_explicit_webhook_url(test_settings) -> None:
    settings = test_settings.model_copy(
        update={
            "API_PUBLIC_URL": "http://backend.test",
            "KB_LOCAL_BASE_URL": "http://kb.test",
            "KB_API_SECRET": "test-kb-secret",
        }
    )
    provider = _RecordingLocalKBProvider(settings)
    request = KBDocumentIngestRequest(
        organization_id=uuid4(),
        playbook_document_id=uuid4(),
        source_uri="http://storage.test/document.pdf",
        filename="document.pdf",
        content_type="application/pdf",
        size_bytes=123,
        source_title="Document",
        status_webhook_url="http://custom.test/hook",
    )

    await provider.ingest_document(request)

    assert provider.posts[0][1]["status_webhook_url"] == "http://custom.test/hook"


@pytest.mark.asyncio
async def test_local_kb_provider_ingest_source_sends_conversation_file_payload(
    test_settings,
) -> None:
    settings = test_settings.model_copy(
        update={
            "API_PUBLIC_URL": "http://backend.test",
            "KB_LOCAL_BASE_URL": "http://kb.test",
            "KB_API_SECRET": "test-kb-secret",
        }
    )
    provider = _RecordingLocalKBProvider(settings)
    request = KBConversationFileIngestRequest(
        organization_id=uuid4(),
        conversation_id=uuid4(),
        conversation_file_id=uuid4(),
        source_uri="http://storage.test/contract.pdf?signature=secret",
        filename="contract.pdf",
        content_type="application/pdf",
        size_bytes=123,
        source_title="contract.pdf",
    )

    response = await provider.ingest_source(request)

    path, payload = provider.posts[0]
    assert path == "/api/kb/ingest/document"
    assert payload["source_type"] == "conversation_file"
    assert payload["organization_id"] == str(request.organization_id)
    assert payload["conversation_id"] == str(request.conversation_id)
    assert payload["conversation_file_id"] == str(request.conversation_file_id)
    assert payload["visibility_policy"] == {"scope": "conversation"}
    assert payload["status_webhook_url"] == "http://backend.test/api/v1/kb/webhook"
    assert "playbook_document_id" not in payload
    assert response.source_type == "conversation_file"
    assert response.conversation_id == request.conversation_id
    assert response.conversation_file_id == request.conversation_file_id


@pytest.mark.asyncio
async def test_local_kb_provider_refresh_document_metadata_sends_patch_payload(
    test_settings,
) -> None:
    settings = test_settings.model_copy(
        update={
            "API_PUBLIC_URL": "http://backend.test",
            "KB_LOCAL_BASE_URL": "http://kb.test",
            "KB_API_SECRET": "test-kb-secret",
        }
    )
    provider = _RecordingLocalKBProvider(settings)
    kb_service_document_id = uuid4()
    request = KBDocumentMetadataRefreshRequest(
        source_date=date(2026, 2, 1),
        is_official=True,
        priority=0,
        visibility_policy={"scope": "all_athletes"},
        metadata_tags={
            "collection": "Compliance",
            "tag_slugs": ["compliance"],
            "tags": ["Compliance"],
        },
    )

    response = await provider.refresh_document_metadata(
        str(kb_service_document_id),
        request,
    )

    path, payload = provider.patches[0]
    assert path == f"/api/kb/documents/{kb_service_document_id}/metadata"
    assert payload == {
        "source_date": "2026-02-01",
        "is_official": True,
        "priority": 0,
        "visibility_policy": {"scope": "all_athletes"},
        "metadata_tags": {
            "collection": "Compliance",
            "tag_slugs": ["compliance"],
            "tags": ["Compliance"],
        },
    }
    assert response.kb_service_document_id == kb_service_document_id
    assert response.updated_embedding_count == 3


@pytest.mark.asyncio
async def test_local_kb_provider_search_admin_uploads_sends_source_type(
    test_settings,
) -> None:
    provider = _SearchRecordingLocalKBProvider(
        test_settings,
        {"results": [], "query": "nil disclosure", "total": 0},
    )
    organization_id = uuid4()

    await provider.search_admin_uploads(
        query="nil disclosure",
        organization_id=organization_id,
        metadata_filter={"visibility_policy": {"scope": "all_athletes"}},
    )

    path, payload = provider.posts[0]
    assert path == "/api/kb/search"
    assert payload["organization_id"] == str(organization_id)
    assert payload["source_types"] == ["admin_upload"]
    assert payload["visibility_context"] == {
        "role": "athlete",
        "visibility_policy": {"scope": "all_athletes"},
    }


@pytest.mark.asyncio
async def test_local_kb_provider_search_conversation_files_sends_private_scope(
    test_settings,
) -> None:
    conversation_id = uuid4()
    file_id = uuid4()
    provider = _SearchRecordingLocalKBProvider(
        test_settings,
        {
            "results": [
                {
                    "document_id": str(file_id),
                    "kb_service_document_id": str(uuid4()),
                    "chunk_id": str(uuid4()),
                    "chunk_index": 2,
                    "text": "The contract requires department approval.",
                    "score": 0.91,
                    "metadata": {
                        "source_type": "conversation_file",
                        "organization_id": "org-id",
                        "conversation_id": str(conversation_id),
                        "conversation_file_id": str(file_id),
                        "source_title": "contract.pdf",
                        "source_summary": "A short orientation summary.",
                        "source_locator": {"type": "page", "page_number": 4},
                    },
                }
            ],
            "query": "approval",
            "total": 1,
        },
    )
    organization_id = uuid4()

    result = await provider.search_conversation_files(
        query="approval",
        organization_id=organization_id,
        conversation_id=conversation_id,
        file_ids=[file_id],
        max_docs=3,
        score_threshold=0.65,
    )

    path, payload = provider.posts[0]
    assert path == "/api/kb/search"
    assert payload["organization_id"] == str(organization_id)
    assert payload["source_types"] == ["conversation_file"]
    assert payload["conversation_id"] == str(conversation_id)
    assert payload["file_ids"] == [str(file_id)]
    assert payload["limit"] == 3
    assert payload["score_threshold"] == 0.65
    assert result.sources[0].metadata["source_type"] == "conversation_file"
    assert result.sources[0].metadata["conversation_id"] == str(conversation_id)
    assert result.sources[0].metadata["conversation_file_id"] == str(file_id)
    assert result.sources[0].metadata["source_summary"] == (
        "A short orientation summary."
    )
    assert result.sources[0].metadata["source_locator"] == {
        "type": "page",
        "page_number": 4,
    }


@pytest.mark.asyncio
async def test_local_kb_provider_preserves_kb_service_result_order(
    test_settings,
) -> None:
    provider = _SearchRecordingLocalKBProvider(
        test_settings,
        {
            "results": [
                {
                    "document_id": "00000000-0000-0000-0000-000000000011",
                    "kb_service_document_id": "00000000-0000-0000-0000-000000000021",
                    "chunk_id": "00000000-0000-0000-0000-000000000012",
                    "chunk_index": 1,
                    "text": "Older lower-scored guidance appears first.",
                    "score": 0.81,
                    "metadata": {
                        "source_title": "Older First Guide",
                        "source_date": "2026-01-01",
                        "ranking_strategy": "hybrid_rerank",
                        "rerank_score": 0.81,
                    },
                },
                {
                    "document_id": "00000000-0000-0000-0000-000000000031",
                    "kb_service_document_id": "00000000-0000-0000-0000-000000000041",
                    "chunk_id": "00000000-0000-0000-0000-000000000032",
                    "chunk_index": 2,
                    "text": "Newer higher-scored guidance appears second.",
                    "score": 0.99,
                    "metadata": {
                        "source_title": "Newer Second Guide",
                        "source_date": "2026-03-01",
                        "ranking_strategy": "hybrid_rerank",
                        "rerank_score": 0.99,
                    },
                },
            ],
            "query": "nil disclosure",
            "total": 2,
        },
    )

    result = await provider.search("nil disclosure", organization_id=uuid4())

    assert [chunk.metadata["source_title"] for chunk in result.sources] == [
        "Older First Guide",
        "Newer Second Guide",
    ]
    assert result.confidence == 0.81
    assert result.context.index("Older lower-scored guidance") < result.context.index(
        "Newer higher-scored guidance"
    )


@pytest.mark.asyncio
async def test_local_kb_provider_defensive_dedupe_keeps_first_seen_chunk(
    test_settings,
) -> None:
    duplicate_chunk_id = "00000000-0000-0000-0000-000000000012"
    provider = _SearchRecordingLocalKBProvider(
        test_settings,
        {
            "results": [
                {
                    "document_id": "00000000-0000-0000-0000-000000000011",
                    "kb_service_document_id": "00000000-0000-0000-0000-000000000021",
                    "chunk_id": duplicate_chunk_id,
                    "chunk_index": 1,
                    "text": "The first chunk identity should win.",
                    "score": 0.71,
                    "metadata": {
                        "source_title": "First Duplicate",
                        "semantic_score": 0.88,
                        "semantic_rank": 1,
                        "hybrid_score": 0.04,
                        "rerank_score": 0.71,
                        "ranking_strategy": "hybrid_rerank",
                    },
                },
                {
                    "document_id": "00000000-0000-0000-0000-000000000031",
                    "kb_service_document_id": "00000000-0000-0000-0000-000000000041",
                    "chunk_id": duplicate_chunk_id,
                    "chunk_index": 9,
                    "text": "The later duplicate must not replace the first.",
                    "score": 0.99,
                    "metadata": {
                        "source_title": "Later Duplicate",
                        "semantic_score": 0.99,
                        "semantic_rank": 2,
                        "hybrid_score": 0.05,
                        "rerank_score": 0.99,
                        "ranking_strategy": "hybrid_rerank",
                    },
                },
                {
                    "document_id": "00000000-0000-0000-0000-000000000051",
                    "kb_service_document_id": "00000000-0000-0000-0000-000000000061",
                    "chunk_id": None,
                    "chunk_index": 3,
                    "text": "Exact duplicate text should keep first text result.",
                    "score": 0.62,
                    "metadata": {"source_title": "First Text Duplicate"},
                },
                {
                    "document_id": "00000000-0000-0000-0000-000000000071",
                    "kb_service_document_id": "00000000-0000-0000-0000-000000000081",
                    "chunk_id": None,
                    "chunk_index": 4,
                    "text": "Exact duplicate text should keep first text result.",
                    "score": 0.97,
                    "metadata": {"source_title": "Later Text Duplicate"},
                },
                {
                    "document_id": "00000000-0000-0000-0000-000000000091",
                    "kb_service_document_id": "00000000-0000-0000-0000-000000000092",
                    "chunk_id": None,
                    "chunk_index": 5,
                    "text": "",
                    "score": 0.3,
                    "metadata": {"source_title": "Empty Text One"},
                },
                {
                    "document_id": "00000000-0000-0000-0000-000000000093",
                    "kb_service_document_id": "00000000-0000-0000-0000-000000000094",
                    "chunk_id": None,
                    "chunk_index": 6,
                    "text": "",
                    "score": 0.2,
                    "metadata": {"source_title": "Empty Text Two"},
                },
            ],
            "query": "nil disclosure",
            "total": 6,
        },
    )

    result = await provider.search("nil disclosure", organization_id=uuid4())

    assert [chunk.metadata["source_title"] for chunk in result.sources] == [
        "First Duplicate",
        "First Text Duplicate",
        "Empty Text One",
        "Empty Text Two",
    ]
    first = result.sources[0]
    assert first.text == "The first chunk identity should win."
    assert first.similarity_score == 0.71
    assert first.metadata["document_id"] == "00000000-0000-0000-0000-000000000011"
    assert first.metadata["kb_service_document_id"] == (
        "00000000-0000-0000-0000-000000000021"
    )
    assert first.metadata["chunk_id"] == duplicate_chunk_id
    assert first.metadata["score"] == 0.71
    assert first.metadata["semantic_score"] == 0.88
    assert first.metadata["hybrid_score"] == 0.04
    assert first.metadata["rerank_score"] == 0.71
    assert first.metadata["ranking_strategy"] == "hybrid_rerank"
