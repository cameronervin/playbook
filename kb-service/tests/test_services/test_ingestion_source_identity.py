from __future__ import annotations

from uuid import uuid4

from app.schemas.ingest import IngestConversationFileRequest, IngestDocumentRequest
from app.services.ingestion.source_identity import (
    dedupe_md5_for_ingest_request,
    metadata_matches_trusted_source_identity,
)


def test_conversation_file_dedupe_hash_is_scoped_but_admin_hash_stays_raw() -> None:
    raw_md5 = "f" * 32
    admin_request = IngestDocumentRequest(
        organization_id=uuid4(),
        playbook_document_id=uuid4(),
        configuration_id=uuid4(),
        source_uri="s3://bucket/nil.pdf",
        filename="nil.pdf",
        content_type="application/pdf",
        size_bytes=100,
        source_title="NIL Handbook",
    )
    file_request = IngestConversationFileRequest(
        organization_id=admin_request.organization_id,
        conversation_id=uuid4(),
        conversation_file_id=uuid4(),
        configuration_id=admin_request.configuration_id,
        source_uri="s3://bucket/contract.pdf",
        filename="contract.pdf",
        content_type="application/pdf",
        size_bytes=100,
        source_title="Contract",
    )

    assert dedupe_md5_for_ingest_request(admin_request, raw_md5) == raw_md5
    scoped = dedupe_md5_for_ingest_request(file_request, raw_md5)
    assert scoped != raw_md5
    assert len(scoped) == 32


def test_admin_source_identity_requires_trusted_ids_to_match() -> None:
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

    assert metadata_matches_trusted_source_identity(
        {
            "source_type": "admin_upload",
            "organization_id": str(request.organization_id),
            "playbook_document_id": str(request.playbook_document_id),
        },
        request,
    )
    assert not metadata_matches_trusted_source_identity(
        {
            "source_type": "admin_upload",
            "organization_id": str(request.organization_id),
            "playbook_document_id": str(uuid4()),
        },
        request,
    )


def test_conversation_file_source_identity_requires_private_scope() -> None:
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

    assert metadata_matches_trusted_source_identity(
        {
            "source_type": "conversation_file",
            "organization_id": str(request.organization_id),
            "conversation_id": str(request.conversation_id),
            "conversation_file_id": str(request.conversation_file_id),
            "visibility_policy": {"scope": "conversation"},
        },
        request,
    )
    assert not metadata_matches_trusted_source_identity(
        {
            "source_type": "conversation_file",
            "organization_id": str(request.organization_id),
            "conversation_id": str(request.conversation_id),
            "conversation_file_id": str(request.conversation_file_id),
            "visibility_policy": {"scope": "all_athletes"},
        },
        request,
    )
