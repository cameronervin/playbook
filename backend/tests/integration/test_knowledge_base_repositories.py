"""Integration tests for Playbook knowledge base repositories."""

from datetime import UTC, date, datetime
from uuid import uuid4

import pytest

from app.repositories.identity import OrganizationRepository, UserRepository
from app.repositories.knowledge_base import (
    KBDocumentEventRepository,
    KBDocumentRepository,
)


@pytest.mark.asyncio
async def test_kb_document_repository_manages_document_metadata_and_status(
    db_session,
):
    org_repo = OrganizationRepository(db_session)
    user_repo = UserRepository(db_session)
    document_repo = KBDocumentRepository(db_session)
    organization = await org_repo.create(name="Playbook Athletics", slug="playbook")
    admin = await user_repo.create(
        organization_id=organization.id,
        email="admin@example.com",
        name="Admin User",
        auth_provider="google",
        provider_subject="admin-google-subject",
        role="admin",
    )

    document = await document_repo.create(
        organization_id=organization.id,
        uploaded_by=admin.id,
        title="NIL Handbook",
        filename="nil-handbook.pdf",
        content_type="application/pdf",
        size_bytes=12345,
        storage_key="kb/originals/org/doc/nil-handbook.pdf",
        metadata_tags={"topic": "nil"},
        source_date=date(2026, 1, 15),
        is_official=True,
        priority=10,
    )

    assert document.id is not None
    assert document.processing_status == "uploaded"
    assert document.visibility_policy == {"scope": "all_athletes"}

    by_id = await document_repo.get_for_organization(
        organization_id=organization.id,
        document_id=document.id,
    )
    documents = await document_repo.list_by_organization(organization.id)

    assert by_id is document
    assert documents == [document]

    await document_repo.update_metadata(
        document,
        metadata_tags={"topic": "compliance"},
        source_date=date(2026, 2, 1),
        is_official=False,
        priority=3,
    )
    await document_repo.update_status(
        document,
        processing_status="failed",
        failure_reason="No extractable text",
    )
    kb_service_document_id = uuid4()
    await document_repo.link_kb_service_document(
        document,
        kb_service_document_id=kb_service_document_id,
    )
    await document_repo.update_ingestion_mirror(
        document,
        summary="NIL handbook orientation summary.",
        chunk_count=12,
    )

    assert document.metadata_tags == {"topic": "compliance"}
    assert document.source_date == date(2026, 2, 1)
    assert document.is_official is False
    assert document.priority == 3
    assert document.processing_status == "failed"
    assert document.failure_reason == "No extractable text"
    assert document.kb_service_document_id == kb_service_document_id
    assert document.summary == "NIL handbook orientation summary."
    assert document.chunk_count == 12


@pytest.mark.asyncio
async def test_kb_document_event_repository_appends_and_lists_events(db_session):
    org_repo = OrganizationRepository(db_session)
    user_repo = UserRepository(db_session)
    document_repo = KBDocumentRepository(db_session)
    event_repo = KBDocumentEventRepository(db_session)
    organization = await org_repo.create(name="Playbook Athletics", slug="playbook")
    admin = await user_repo.create(
        organization_id=organization.id,
        email="admin@example.com",
        name="Admin User",
        auth_provider="google",
        provider_subject="admin-google-subject",
        role="admin",
    )
    document = await document_repo.create(
        organization_id=organization.id,
        uploaded_by=admin.id,
        title="NIL Handbook",
        filename="nil-handbook.pdf",
        content_type="application/pdf",
        size_bytes=12345,
        storage_key="kb/originals/org/doc/nil-handbook.pdf",
    )

    created_event = await event_repo.create(
        document_id=document.id,
        event_type="ingestion.started",
        status="processing",
        message="Started ingestion",
        metadata={"stage": "parse"},
        created_at=datetime(2026, 1, 1, tzinfo=UTC),
    )
    ready_event = await event_repo.create(
        document_id=document.id,
        event_type="ingestion.completed",
        status="ready",
        message=None,
        metadata={"chunk_count": 42},
        created_at=datetime(2026, 1, 2, tzinfo=UTC),
    )

    events = await event_repo.list_by_document(document.id)

    assert events == [created_event, ready_event]
