from __future__ import annotations

from uuid import uuid4

import pytest

from app.infrastructure.knowledgebase.providers.local_kb import LocalKBProvider
from app.schemas.knowledgebase import (
    KBConversationFileIngestRequest,
    KBDocumentIngestRequest,
)


class _RecordingLocalKBProvider(LocalKBProvider):
    def __init__(self, settings) -> None:
        super().__init__(settings)
        self.posts: list[tuple[str, dict]] = []

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
