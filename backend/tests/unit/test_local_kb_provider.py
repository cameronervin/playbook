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
