from __future__ import annotations

from uuid import uuid4

import pytest
from pydantic import TypeAdapter, ValidationError

from app.core.config import Settings
from app.schemas.ingest import (
    IngestConversationFileRequest,
    IngestDocumentRequest,
    IngestSourceRequest,
)
from tests.fakes.kb_contracts import (
    FakePrivateRetrieval,
    FakeSummaryProvider,
    build_ingest_metadata,
)


def _base_settings(**overrides: object) -> Settings:
    values = {
        "DATABASE_URL": "postgresql+asyncpg://kb:kb@localhost:5432/kb",
        "KB_WEBHOOK_SECRET": "long-webhook-secret-value-123456",
        "KB_API_SECRET": "long-api-secret-value-1234567890",
        "LLM_PROVIDER_MODE": "litellm",
        "LITELLM_BASE_URL": "http://litellm:4000",
        "LITELLM_API_KEY": "litellm-key",
    }
    values.update(overrides)
    return Settings(_env_file=None, **values)


def test_summary_config_defaults_load_from_settings() -> None:
    settings = _base_settings()

    assert settings.LITELLM_SUMMARY_MODEL == "playbook-fast"
    assert settings.KB_SUMMARY_INPUT_MAX_TOKENS == 3000
    assert settings.KB_SUMMARY_MAX_OUTPUT_TOKENS == 160


def test_kb_service_contract_accepts_admin_upload_metadata() -> None:
    request = TypeAdapter(IngestSourceRequest).validate_python(
        {
            "source_type": "admin_upload",
            "organization_id": str(uuid4()),
            "playbook_document_id": str(uuid4()),
            "configuration_id": str(uuid4()),
            "source_uri": "s3://playbook-bucket/kb/originals/nil.pdf",
            "filename": "nil.pdf",
            "content_type": "application/pdf",
            "size_bytes": 100,
            "source_title": "NIL Handbook",
        }
    )

    assert isinstance(request, IngestDocumentRequest)
    assert request.source_type == "admin_upload"
    assert request.visibility_policy == {"scope": "all_athletes"}


def test_kb_service_contract_accepts_conversation_file_metadata() -> None:
    request = TypeAdapter(IngestSourceRequest).validate_python(
        {
            "source_type": "conversation_file",
            "organization_id": str(uuid4()),
            "conversation_id": str(uuid4()),
            "conversation_file_id": str(uuid4()),
            "configuration_id": str(uuid4()),
            "source_uri": "s3://playbook-bucket/conversations/contract.pdf",
            "filename": "contract.pdf",
            "content_type": "application/pdf",
            "size_bytes": 100,
            "source_title": "Contract",
        }
    )

    assert isinstance(request, IngestConversationFileRequest)
    assert request.source_type == "conversation_file"
    assert request.visibility_policy == {"scope": "conversation"}


def test_kb_service_contract_rejects_missing_required_source_ids() -> None:
    with pytest.raises(ValidationError) as admin_exc:
        TypeAdapter(IngestSourceRequest).validate_python(
            {
                "source_type": "admin_upload",
                "organization_id": str(uuid4()),
                "configuration_id": str(uuid4()),
                "source_uri": "s3://bucket/nil.pdf",
                "filename": "nil.pdf",
                "content_type": "application/pdf",
                "size_bytes": 100,
                "source_title": "NIL Handbook",
            }
        )
    with pytest.raises(ValidationError) as file_exc:
        TypeAdapter(IngestSourceRequest).validate_python(
            {
                "source_type": "conversation_file",
                "organization_id": str(uuid4()),
                "configuration_id": str(uuid4()),
                "source_uri": "s3://bucket/contract.pdf",
                "filename": "contract.pdf",
                "content_type": "application/pdf",
                "size_bytes": 100,
                "source_title": "Contract",
            }
        )

    assert "playbook_document_id" in str(admin_exc.value)
    assert "conversation_id" in str(file_exc.value)
    assert "conversation_file_id" in str(file_exc.value)


def test_build_ingest_metadata_stamps_source_type_and_private_scope() -> None:
    request = IngestConversationFileRequest(
        organization_id=uuid4(),
        conversation_id=uuid4(),
        conversation_file_id=uuid4(),
        configuration_id=uuid4(),
        source_uri="s3://bucket/contract.pdf",
        filename="contract.pdf",
        content_type="application/pdf",
        size_bytes=100,
        source_title="Contract",
    )

    metadata = build_ingest_metadata(request)

    assert metadata["source_type"] == "conversation_file"
    assert metadata["conversation_id"] == str(request.conversation_id)
    assert metadata["conversation_file_id"] == str(request.conversation_file_id)
    assert metadata["visibility_policy"] == {"scope": "conversation"}
    assert "source_uri" not in metadata


def test_admin_upload_idempotency_identity_is_backend_document_id() -> None:
    playbook_document_id = uuid4()
    organization_id = uuid4()
    first = IngestDocumentRequest(
        organization_id=organization_id,
        playbook_document_id=playbook_document_id,
        configuration_id=uuid4(),
        source_uri="https://storage.test/bucket/first.pdf?signature=secret",
        filename="first.pdf",
        content_type="application/pdf",
        size_bytes=100,
        source_title="First",
    )
    second = first.model_copy(
        update={
            "source_uri": "https://storage.test/bucket/second.pdf?signature=secret",
            "filename": "second.pdf",
            "source_title": "Second",
        }
    )

    first_identity = {
        key: build_ingest_metadata(first)[key]
        for key in ("source_type", "organization_id", "playbook_document_id")
    }
    second_identity = {
        key: build_ingest_metadata(second)[key]
        for key in ("source_type", "organization_id", "playbook_document_id")
    }

    assert first_identity == second_identity


def test_conversation_file_idempotency_identity_is_trusted_private_scope() -> None:
    organization_id = uuid4()
    conversation_id = uuid4()
    conversation_file_id = uuid4()
    first = IngestConversationFileRequest(
        organization_id=organization_id,
        conversation_id=conversation_id,
        conversation_file_id=conversation_file_id,
        configuration_id=uuid4(),
        source_uri="https://storage.test/bucket/first.pdf?signature=secret",
        filename="first.pdf",
        content_type="application/pdf",
        size_bytes=100,
        source_title="First",
    )
    second = first.model_copy(
        update={
            "source_uri": "https://storage.test/bucket/second.pdf?signature=secret",
            "filename": "second.pdf",
            "source_title": "Second",
        }
    )

    identity_keys = (
        "source_type",
        "organization_id",
        "conversation_id",
        "conversation_file_id",
        "visibility_policy",
    )
    first_identity = {key: build_ingest_metadata(first)[key] for key in identity_keys}
    second_identity = {key: build_ingest_metadata(second)[key] for key in identity_keys}

    assert first_identity == second_identity


@pytest.mark.asyncio
async def test_private_retrieval_fake_rejects_cross_conversation_leaks() -> None:
    organization_id = uuid4()
    conversation_id = uuid4()
    other_conversation_id = uuid4()
    retrieval = FakePrivateRetrieval(
        [
            {
                "text": "Shared NIL guidance",
                "metadata": {
                    "organization_id": str(organization_id),
                    "source_type": "admin_upload",
                    "visibility_policy": {"scope": "all_athletes"},
                },
            },
            {
                "text": "Private contract clause",
                "metadata": {
                    "organization_id": str(organization_id),
                    "source_type": "conversation_file",
                    "conversation_id": str(conversation_id),
                    "visibility_policy": {"scope": "conversation"},
                },
            },
        ]
    )

    shared = await retrieval.search(
        organization_id=organization_id,
        source_type="admin_upload",
    )
    missing_scope = await retrieval.search(
        organization_id=organization_id,
        source_type="conversation_file",
    )
    wrong_scope = await retrieval.search(
        organization_id=organization_id,
        source_type="conversation_file",
        conversation_id=other_conversation_id,
    )
    private = await retrieval.search(
        organization_id=organization_id,
        source_type="conversation_file",
        conversation_id=conversation_id,
    )

    assert [item["text"] for item in shared] == ["Shared NIL guidance"]
    assert missing_scope == []
    assert wrong_scope == []
    assert [item["text"] for item in private] == ["Private contract clause"]


def test_summary_fake_returns_deterministic_summary_and_extract_fallback() -> None:
    provider = FakeSummaryProvider()
    fallback_provider = FakeSummaryProvider(should_fail=True)

    summary = provider.summarize(
        filename="contract.pdf",
        text="This agreement covers NIL appearance obligations.",
    )
    fallback = fallback_provider.summarize(
        filename="contract.pdf",
        text="This agreement covers NIL appearance obligations.",
    )

    assert summary == "Summary for contract.pdf: This agreement covers NIL appearance obligations."
    assert fallback == "contract.pdf: This agreement covers NIL appearance obligations."
