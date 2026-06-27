from __future__ import annotations

import json
from uuid import uuid4

import pytest
from pydantic import TypeAdapter, ValidationError

from app.schemas.kb_documents import KBWebhookPayload
from app.schemas.knowledgebase import (
    KBConversationFileIngestRequest,
    KBDocumentIngestRequest,
    KBIngestRequest,
    RetrievedChunk,
)
from tests.fakes.knowledgebase import (
    FakeKBDispatchRecorder,
    FakeScopedRetrievalProvider,
    sign_kb_webhook_payload,
)


def test_kb_ingest_contract_accepts_admin_upload_source_type() -> None:
    request = TypeAdapter(KBIngestRequest).validate_python(
        {
            "source_type": "admin_upload",
            "organization_id": str(uuid4()),
            "playbook_document_id": str(uuid4()),
            "source_uri": "https://storage.test/nil.pdf?signature=secret",
            "filename": "nil.pdf",
            "content_type": "application/pdf",
            "size_bytes": 100,
            "source_title": "NIL Handbook",
        }
    )

    assert isinstance(request, KBDocumentIngestRequest)
    assert request.source_type == "admin_upload"
    assert request.visibility_policy == {"scope": "all_athletes"}


def test_kb_ingest_contract_accepts_conversation_file_source_type() -> None:
    request = TypeAdapter(KBIngestRequest).validate_python(
        {
            "source_type": "conversation_file",
            "organization_id": str(uuid4()),
            "conversation_id": str(uuid4()),
            "conversation_file_id": str(uuid4()),
            "source_uri": "https://storage.test/contract.pdf?signature=secret",
            "filename": "contract.pdf",
            "content_type": "application/pdf",
            "size_bytes": 100,
            "source_title": "Contract",
        }
    )

    assert isinstance(request, KBConversationFileIngestRequest)
    assert request.source_type == "conversation_file"
    assert request.visibility_policy == {"scope": "conversation"}


def test_kb_ingest_contract_rejects_admin_upload_without_playbook_document_id() -> None:
    with pytest.raises(ValidationError) as exc_info:
        TypeAdapter(KBIngestRequest).validate_python(
            {
                "source_type": "admin_upload",
                "organization_id": str(uuid4()),
                "source_uri": "https://storage.test/nil.pdf",
                "filename": "nil.pdf",
                "content_type": "application/pdf",
                "size_bytes": 100,
                "source_title": "NIL Handbook",
            }
        )

    assert "playbook_document_id" in str(exc_info.value)


def test_kb_ingest_contract_rejects_conversation_file_without_private_ids() -> None:
    with pytest.raises(ValidationError) as exc_info:
        TypeAdapter(KBIngestRequest).validate_python(
            {
                "source_type": "conversation_file",
                "organization_id": str(uuid4()),
                "source_uri": "https://storage.test/contract.pdf",
                "filename": "contract.pdf",
                "content_type": "application/pdf",
                "size_bytes": 100,
                "source_title": "Contract",
            }
        )

    message = str(exc_info.value)
    assert "conversation_id" in message
    assert "conversation_file_id" in message


@pytest.mark.asyncio
async def test_fake_dispatch_records_both_source_types_without_external_services() -> None:
    recorder = FakeKBDispatchRecorder()
    admin_request = KBDocumentIngestRequest(
        organization_id=uuid4(),
        playbook_document_id=uuid4(),
        source_uri="https://storage.test/nil.pdf?signature=secret",
        filename="nil.pdf",
        content_type="application/pdf",
        size_bytes=100,
        source_title="NIL Handbook",
    )
    file_request = KBConversationFileIngestRequest(
        organization_id=admin_request.organization_id,
        conversation_id=uuid4(),
        conversation_file_id=uuid4(),
        source_uri="https://storage.test/contract.pdf?signature=secret",
        filename="contract.pdf",
        content_type="application/pdf",
        size_bytes=100,
        source_title="Contract",
    )

    await recorder.dispatch(admin_request)
    await recorder.dispatch(file_request)

    assert [request.source_type for request in recorder.requests] == [
        "admin_upload",
        "conversation_file",
    ]
    assert recorder.requests[1].source_uri.startswith("https://storage.test/")


@pytest.mark.asyncio
async def test_fake_retrieval_requires_private_scope_for_conversation_files() -> None:
    organization_id = uuid4()
    conversation_id = uuid4()
    other_conversation_id = uuid4()
    provider = FakeScopedRetrievalProvider(
        [
            RetrievedChunk(
                text="Shared NIL policy",
                metadata={
                    "organization_id": str(organization_id),
                    "source_type": "admin_upload",
                    "visibility_policy": {"scope": "all_athletes"},
                },
                similarity_score=0.9,
            ),
            RetrievedChunk(
                text="Private contract clause",
                metadata={
                    "organization_id": str(organization_id),
                    "source_type": "conversation_file",
                    "conversation_id": str(conversation_id),
                    "visibility_policy": {"scope": "conversation"},
                },
                similarity_score=0.91,
            ),
        ]
    )

    shared = await provider.search(
        "nil",
        organization_id,
        metadata_filter={"source_type": "admin_upload"},
    )
    other_private = await provider.search(
        "contract",
        organization_id,
        metadata_filter={
            "source_type": "conversation_file",
            "conversation_id": str(other_conversation_id),
        },
    )
    private = await provider.search(
        "contract",
        organization_id,
        metadata_filter={
            "source_type": "conversation_file",
            "conversation_id": str(conversation_id),
        },
    )

    assert [source.text for source in shared.sources] == ["Shared NIL policy"]
    assert other_private.sources == []
    assert [source.text for source in private.sources] == ["Private contract clause"]


def test_fake_signed_webhook_supports_source_identity_without_sensitive_values() -> None:
    payload = {
        "document_id": str(uuid4()),
        "kb_service_document_id": str(uuid4()),
        "source_type": "conversation_file",
        "conversation_id": str(uuid4()),
        "conversation_file_id": str(uuid4()),
        "stage": "pipeline",
        "status": "success",
        "summary": "One-sentence orientation summary.",
        "metadata": {
            "chunk_count": 3,
            "source_uri": "https://storage.test/file.pdf?signature=secret",
            "raw_text": "private contract text",
        },
    }

    body, signature = sign_kb_webhook_payload(payload, "webhook-secret")
    validated = KBWebhookPayload.model_validate_json(body)
    rendered_body = body.decode()
    rendered_metadata = json.dumps(validated.metadata)

    assert signature.startswith("sha256=")
    assert validated.source_type == "conversation_file"
    assert validated.conversation_file_id is not None
    assert "signature=secret" not in rendered_body
    assert "private contract text" not in rendered_metadata
