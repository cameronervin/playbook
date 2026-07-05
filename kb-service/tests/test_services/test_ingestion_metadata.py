from __future__ import annotations

from uuid import uuid4

import pytest
from fastapi import HTTPException

from app.schemas.ingest import IngestConversationFileRequest, IngestDocumentRequest
from app.services.ingestion.metadata import (
    metadata_from_ingest_request,
    metadata_with_organization,
)


def test_metadata_with_organization_stamps_missing_scope() -> None:
    organization_id = uuid4()

    metadata = metadata_with_organization(
        {"source_title": "NIL Handbook"},
        organization_id=organization_id,
    )

    assert metadata["organization_id"] == str(organization_id)
    assert metadata["source_title"] == "NIL Handbook"


def test_metadata_with_organization_rejects_conflicting_scope() -> None:
    organization_id = uuid4()

    with pytest.raises(HTTPException) as exc_info:
        metadata_with_organization(
            {"organization_id": str(uuid4())},
            organization_id=organization_id,
        )

    assert exc_info.value.status_code == 400
    assert "organization_id" in str(exc_info.value.detail)


def test_ingest_metadata_normalizes_admin_documents_as_official_without_priority() -> None:
    request = IngestDocumentRequest(
        organization_id=uuid4(),
        playbook_document_id=uuid4(),
        configuration_id=uuid4(),
        source_uri="s3://bucket/nil.pdf",
        filename="nil.pdf",
        content_type="application/pdf",
        size_bytes=100,
        source_title="NIL Handbook",
        is_official=False,
        priority=10,
        metadata_tags={"topic": "nil"},
    )

    metadata = metadata_from_ingest_request(request)

    assert metadata["is_official"] is True
    assert metadata["priority"] == 0
    assert metadata["metadata_tags"] == {"topic": "nil"}


def test_ingest_metadata_disables_webhook_when_url_is_omitted() -> None:
    request = IngestDocumentRequest(
        organization_id=uuid4(),
        playbook_document_id=uuid4(),
        configuration_id=uuid4(),
        source_uri="s3://bucket/nil.pdf",
        filename="nil.pdf",
        content_type="application/pdf",
        size_bytes=100,
        source_title="NIL Handbook",
    )

    metadata = metadata_from_ingest_request(request)

    assert metadata["webhook_enabled"] is False
    assert metadata["status_webhook_url"] is None


def test_ingest_metadata_enables_webhook_when_url_is_supplied() -> None:
    request = IngestDocumentRequest(
        organization_id=uuid4(),
        playbook_document_id=uuid4(),
        configuration_id=uuid4(),
        source_uri="s3://bucket/nil.pdf",
        filename="nil.pdf",
        content_type="application/pdf",
        size_bytes=100,
        source_title="NIL Handbook",
        status_webhook_url="http://backend.test/api/v1/kb/webhook",
    )

    metadata = metadata_from_ingest_request(request)

    assert metadata["webhook_enabled"] is True
    assert metadata["status_webhook_url"] == "http://backend.test/api/v1/kb/webhook"


def test_ingest_metadata_stamps_conversation_file_private_scope_without_source_uri() -> None:
    request = IngestConversationFileRequest(
        organization_id=uuid4(),
        conversation_id=uuid4(),
        conversation_file_id=uuid4(),
        configuration_id=uuid4(),
        source_uri="https://storage.test/contract.pdf?signature=secret",
        filename="contract.pdf",
        content_type="application/pdf",
        size_bytes=100,
        source_title="Contract",
    )

    metadata = metadata_from_ingest_request(request)

    assert metadata["source_type"] == "conversation_file"
    assert metadata["organization_id"] == str(request.organization_id)
    assert metadata["conversation_id"] == str(request.conversation_id)
    assert metadata["conversation_file_id"] == str(request.conversation_file_id)
    assert metadata["visibility_policy"] == {"scope": "conversation"}
    assert "playbook_document_id" not in metadata
    assert "source_uri" not in metadata
    assert "signature=secret" not in str(metadata)


def test_ingest_metadata_rejects_conversation_file_without_conversation_visibility() -> None:
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
        visibility_policy={"scope": "all_athletes"},
    )

    with pytest.raises(HTTPException) as exc_info:
        metadata_from_ingest_request(request)

    assert exc_info.value.status_code == 400
    assert "visibility_policy.scope" in str(exc_info.value.detail)
