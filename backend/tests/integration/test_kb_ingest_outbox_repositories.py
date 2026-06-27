"""Integration tests for durable KB ingest outbox repositories."""

from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest
from sqlalchemy.dialects import postgresql

from app.repositories.conversations import ConversationFileRepository, ConversationRepository
from app.repositories.identity import OrganizationRepository, UserRepository
from app.repositories.knowledge_base import KBDocumentRepository
from app.repositories.uploads import KBIngestOutboxRepository


@pytest.mark.asyncio
async def test_kb_ingest_outbox_enqueue_is_idempotent_for_admin_document(db_session):
    organization = await OrganizationRepository(db_session).create(
        name="Playbook Athletics",
        slug="playbook-outbox-admin",
    )
    admin = await UserRepository(db_session).create(
        organization_id=organization.id,
        email="admin-outbox@example.com",
        name="Admin User",
        auth_provider="google",
        provider_subject="admin-outbox",
        role="admin",
    )
    document = await KBDocumentRepository(db_session).create(
        organization_id=organization.id,
        uploaded_by=admin.id,
        title="NIL Handbook",
        filename="nil-handbook.pdf",
        content_type="application/pdf",
        size_bytes=123,
        storage_key="kb/originals/document.pdf",
    )
    repository = KBIngestOutboxRepository(db_session)

    first = await repository.enqueue(
        organization_id=organization.id,
        source_type="admin_upload",
        kb_document_id=document.id,
    )
    second = await repository.enqueue(
        organization_id=organization.id,
        source_type="admin_upload",
        kb_document_id=document.id,
    )

    assert second is first
    assert first.status == "pending"
    assert first.attempt_count == 0


@pytest.mark.asyncio
async def test_kb_ingest_outbox_due_rows_and_status_transitions(db_session):
    organization = await OrganizationRepository(db_session).create(
        name="Playbook Athletics",
        slug="playbook-outbox-file",
    )
    athlete = await UserRepository(db_session).create(
        organization_id=organization.id,
        email="athlete-outbox@example.com",
        name="Jordan Athlete",
        auth_provider="google",
        provider_subject="athlete-outbox",
    )
    conversation = await ConversationRepository(db_session).create(
        organization_id=organization.id,
        athlete_id=athlete.id,
    )
    file = await ConversationFileRepository(db_session).create(
        conversation_id=conversation.id,
        uploaded_by=athlete.id,
        filename="contract.pdf",
        content_type="application/pdf",
        size_bytes=123,
        storage_key="conversation-files/originals/contract.pdf",
    )
    future_file = await ConversationFileRepository(db_session).create(
        conversation_id=conversation.id,
        uploaded_by=athlete.id,
        filename="future-contract.pdf",
        content_type="application/pdf",
        size_bytes=456,
        storage_key="conversation-files/originals/future-contract.pdf",
    )
    repository = KBIngestOutboxRepository(db_session)
    now = datetime.now(UTC)
    due = await repository.enqueue(
        organization_id=organization.id,
        source_type="conversation_file",
        conversation_file_id=file.id,
        next_attempt_at=now - timedelta(seconds=1),
    )
    future = await repository.enqueue(
        organization_id=organization.id,
        source_type="conversation_file",
        conversation_file_id=future_file.id,
        next_attempt_at=now + timedelta(minutes=10),
    )

    due_rows = await repository.list_due_for_update(now=now)
    await repository.mark_dispatched(
        due,
        kb_service_document_id=uuid4(),
        kb_task_id="kb-task-1",
    )
    await repository.schedule_retry(
        future,
        next_attempt_at=now + timedelta(minutes=5),
        failure_metadata={"error_type": "TimeoutError"},
    )
    await repository.mark_failed(
        future,
        failure_metadata={"error_type": "TerminalError"},
    )

    assert due_rows == [due]
    assert due.status == "dispatched"
    assert due.attempt_count == 1
    assert due.kb_task_id == "kb-task-1"
    assert future.status == "failed"
    assert future.failure_metadata == {"error_type": "TerminalError"}


def test_kb_ingest_outbox_due_query_uses_skip_locked() -> None:
    stmt = KBIngestOutboxRepository.due_rows_statement(
        now=datetime.now(UTC),
        limit=25,
    )

    compiled = str(stmt.compile(dialect=postgresql.dialect()))

    assert "FOR UPDATE SKIP LOCKED" in compiled
