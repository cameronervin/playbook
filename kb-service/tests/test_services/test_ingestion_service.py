from __future__ import annotations

from uuid import uuid4

import pytest
from fastapi import HTTPException

from app.schemas.ingest import IngestDocumentRequest
from app.services.ingestion_service import (
    _metadata_from_ingest_request,
    _metadata_with_organization,
)


def test_metadata_with_organization_stamps_missing_scope() -> None:
    organization_id = uuid4()

    metadata = _metadata_with_organization(
        {"source_title": "NIL Handbook"},
        organization_id=organization_id,
    )

    assert metadata["organization_id"] == str(organization_id)
    assert metadata["source_title"] == "NIL Handbook"


def test_metadata_with_organization_rejects_conflicting_scope() -> None:
    organization_id = uuid4()

    with pytest.raises(HTTPException) as exc_info:
        _metadata_with_organization(
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

    metadata = _metadata_from_ingest_request(request)

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

    metadata = _metadata_from_ingest_request(request)

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

    metadata = _metadata_from_ingest_request(request)

    assert metadata["webhook_enabled"] is True
    assert metadata["status_webhook_url"] == "http://backend.test/api/v1/kb/webhook"
