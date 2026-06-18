"""Integration tests for the Phase 9D KB ingest outbox worker service."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any
from uuid import UUID, uuid4

import pytest
from sqlalchemy import select

from app.core.exceptions import KBConnectionError, KBValidationError
from app.models.conversations import ConversationFile
from app.models.knowledge_base import KBDocument, KBDocumentEvent
from app.repositories.conversations import (
    ConversationFileRepository,
    ConversationRepository,
)
from app.repositories.identity import OrganizationRepository, UserRepository
from app.repositories.knowledge_base import KBDocumentRepository
from app.repositories.uploads import KBIngestOutboxRepository
from app.schemas.knowledgebase import (
    KBConversationFileIngestRequest,
    KBDocumentIngestRequest,
    KBDocumentIngestResponse,
    KnowledgebaseResult,
)
from app.services.kb_ingest_outbox import KbIngestOutboxService


class FakeWorkerStorageProvider:
    """Storage fake that records short-lived source URL generation."""

    def __init__(self) -> None:
        self.presigned_urls: list[tuple[str, str | None]] = []

    async def get_presigned_url(
        self,
        key: str,
        expires_in: int = 3600,
        download_filename: str | None = None,
    ) -> str:
        self.presigned_urls.append((key, download_filename))
        return f"https://storage.example/{key}?signature=topsecret"


class FakeWorkerKBProvider:
    """Knowledgebase fake that records trusted ingest requests."""

    def __init__(self, *, failure: Exception | None = None) -> None:
        self.failure = failure
        self.requests: list[KBDocumentIngestRequest | KBConversationFileIngestRequest] = []

    @property
    def provider_name(self) -> str:
        return "fake-worker"

    async def search(
        self,
        query: str,
        organization_id: UUID | str,
        max_docs: int = 10,
        score_threshold: float = 0.7,
        metadata_filter: dict[str, Any] | None = None,
        configuration_id: str | None = None,
    ) -> KnowledgebaseResult:
        return KnowledgebaseResult(
            query=query,
            context="",
            sources=[],
            zero_hit=True,
            latency_ms=1,
        )

    async def health_check(self) -> bool:
        return True

    async def resolve_configuration(self) -> str:
        return "configuration-id"

    async def ingest_source(
        self,
        request: KBDocumentIngestRequest | KBConversationFileIngestRequest,
    ) -> KBDocumentIngestResponse:
        self.requests.append(request)
        if self.failure is not None:
            raise self.failure
        return KBDocumentIngestResponse(
            kb_service_document_id=uuid4(),
            source_type=request.source_type,
            playbook_document_id=(
                request.playbook_document_id
                if isinstance(request, KBDocumentIngestRequest)
                else None
            ),
            conversation_id=(
                request.conversation_id
                if isinstance(request, KBConversationFileIngestRequest)
                else None
            ),
            conversation_file_id=(
                request.conversation_file_id
                if isinstance(request, KBConversationFileIngestRequest)
                else None
            ),
            task_id=f"kb-task-{len(self.requests)}",
            status="pending",
        )


async def _admin_document(db_session) -> tuple[Any, Any, KBDocument]:
    organization = await OrganizationRepository(db_session).create(
        name="Playbook Athletics",
        slug=f"playbook-admin-outbox-{uuid4()}",
    )
    admin = await UserRepository(db_session).create(
        organization_id=organization.id,
        email=f"admin-{uuid4()}@example.com",
        name="Admin User",
        auth_provider="google",
        provider_subject=f"admin-{uuid4()}",
        role="admin",
    )
    document = await KBDocumentRepository(db_session).create(
        organization_id=organization.id,
        uploaded_by=admin.id,
        title="NIL Handbook",
        filename="nil-handbook.pdf",
        content_type="application/pdf",
        size_bytes=123,
        storage_key=f"kb/originals/{organization.id}/nil-handbook.pdf",
        processing_status="uploaded",
        metadata_tags={"topic": "nil"},
        is_official=True,
        priority=0,
    )
    return organization, admin, document


async def _conversation_file(db_session) -> tuple[Any, Any, Any, ConversationFile]:
    organization = await OrganizationRepository(db_session).create(
        name="Playbook Athletics",
        slug=f"playbook-file-outbox-{uuid4()}",
    )
    athlete = await UserRepository(db_session).create(
        organization_id=organization.id,
        email=f"athlete-{uuid4()}@example.com",
        name="Jordan Athlete",
        auth_provider="google",
        provider_subject=f"athlete-{uuid4()}",
    )
    conversation = await ConversationRepository(db_session).create(
        organization_id=organization.id,
        athlete_id=athlete.id,
    )
    file = await ConversationFileRepository(db_session).create(
        conversation_id=conversation.id,
        uploaded_by=athlete.id,
        filename="nil-contract.pdf",
        content_type="application/pdf",
        size_bytes=456,
        storage_key=(
            f"conversation-files/originals/{organization.id}/"
            f"{conversation.id}/nil-contract.pdf"
        ),
        extraction_status="uploaded",
    )
    return organization, athlete, conversation, file


@pytest.mark.asyncio
async def test_outbox_worker_dispatches_admin_document(db_session, test_settings) -> None:
    organization, _admin, document = await _admin_document(db_session)
    organization_id = organization.id
    document_id = document.id
    row = await KBIngestOutboxRepository(db_session).enqueue(
        organization_id=organization_id,
        source_type="admin_upload",
        kb_document_id=document_id,
    )
    storage = FakeWorkerStorageProvider()
    kb_provider = FakeWorkerKBProvider()

    result = await KbIngestOutboxService(
        db_session,
        storage=storage,
        kb_provider=kb_provider,
        settings=test_settings,
    ).drain_due(limit=25)

    assert result.dispatched == 1
    await db_session.refresh(row)
    await db_session.refresh(document)
    assert row.status == "dispatched"
    assert row.kb_service_document_id is not None
    assert row.kb_task_id == "kb-task-1"
    assert document.kb_service_document_id == row.kb_service_document_id
    assert document.processing_status == "processing"
    assert storage.presigned_urls == [(document.storage_key, document.filename)]
    assert len(kb_provider.requests) == 1
    request = kb_provider.requests[0]
    assert isinstance(request, KBDocumentIngestRequest)
    assert request.source_type == "admin_upload"
    assert request.organization_id == organization_id
    assert request.playbook_document_id == document_id
    assert request.source_uri.startswith("https://storage.example/")

    events = list(
        (
            await db_session.scalars(
                select(KBDocumentEvent).where(KBDocumentEvent.document_id == document.id)
            )
        ).all()
    )
    assert [event.event_type for event in events] == ["ingestion.dispatched"]


@pytest.mark.asyncio
async def test_outbox_worker_dispatches_conversation_file(
    db_session,
    test_settings,
) -> None:
    organization, _athlete, conversation, file = await _conversation_file(db_session)
    organization_id = organization.id
    conversation_id = conversation.id
    file_id = file.id
    row = await KBIngestOutboxRepository(db_session).enqueue(
        organization_id=organization_id,
        source_type="conversation_file",
        conversation_file_id=file_id,
    )
    storage = FakeWorkerStorageProvider()
    kb_provider = FakeWorkerKBProvider()

    result = await KbIngestOutboxService(
        db_session,
        storage=storage,
        kb_provider=kb_provider,
        settings=test_settings,
    ).drain_due(limit=25)

    assert result.dispatched == 1
    await db_session.refresh(row)
    await db_session.refresh(file)
    assert row.status == "dispatched"
    assert row.kb_service_document_id is not None
    assert row.kb_task_id == "kb-task-1"
    assert file.kb_service_document_id == row.kb_service_document_id
    assert file.extraction_status == "extracting"
    assert storage.presigned_urls == [(file.storage_key, file.filename)]
    assert len(kb_provider.requests) == 1
    request = kb_provider.requests[0]
    assert isinstance(request, KBConversationFileIngestRequest)
    assert request.source_type == "conversation_file"
    assert request.organization_id == organization_id
    assert request.conversation_id == conversation_id
    assert request.conversation_file_id == file_id


@pytest.mark.asyncio
async def test_outbox_worker_schedules_retry_for_retryable_failure(
    db_session,
    test_settings,
) -> None:
    organization, _admin, document = await _admin_document(db_session)
    row = await KBIngestOutboxRepository(db_session).enqueue(
        organization_id=organization.id,
        source_type="admin_upload",
        kb_document_id=document.id,
    )
    kb_provider = FakeWorkerKBProvider(
        failure=KBConnectionError(
            "KB down for https://storage.example/private.pdf?signature=topsecret"
        )
    )

    result = await KbIngestOutboxService(
        db_session,
        storage=FakeWorkerStorageProvider(),
        kb_provider=kb_provider,
        settings=test_settings,
    ).drain_due(limit=25)

    assert result.retried == 1
    await db_session.refresh(row)
    await db_session.refresh(document)
    assert row.status == "retrying"
    assert row.attempt_count == 1
    assert row.next_attempt_at > datetime.now(UTC)
    assert row.failure_metadata["error_type"] == "KBConnectionError"
    assert row.failure_metadata["retryable"] is True
    assert "topsecret" not in repr(row.failure_metadata)
    assert "https://storage.example" not in repr(row.failure_metadata)
    assert document.processing_status == "uploaded"

    events = list(
        (
            await db_session.scalars(
                select(KBDocumentEvent).where(KBDocumentEvent.document_id == document.id)
            )
        ).all()
    )
    assert [event.event_type for event in events] == ["ingestion.retry_scheduled"]


@pytest.mark.asyncio
async def test_outbox_worker_marks_terminal_failure_with_safe_reason(
    db_session,
    test_settings,
) -> None:
    organization, _admin, document = await _admin_document(db_session)
    row = await KBIngestOutboxRepository(db_session).enqueue(
        organization_id=organization.id,
        source_type="admin_upload",
        kb_document_id=document.id,
    )
    kb_provider = FakeWorkerKBProvider(
        failure=KBValidationError(
            "Rejected https://storage.example/private.pdf?signature=topsecret"
        )
    )

    result = await KbIngestOutboxService(
        db_session,
        storage=FakeWorkerStorageProvider(),
        kb_provider=kb_provider,
        settings=test_settings,
    ).drain_due(limit=25)

    assert result.failed == 1
    await db_session.refresh(row)
    await db_session.refresh(document)
    assert row.status == "failed"
    assert row.failure_metadata["error_type"] == "KBValidationError"
    assert row.failure_metadata["retryable"] is False
    assert "topsecret" not in repr(row.failure_metadata)
    assert row.error_message == "KB ingestion dispatch failed"
    assert document.processing_status == "failed"
    assert document.failure_reason == "KB ingestion dispatch failed"

    events = list(
        (
            await db_session.scalars(
                select(KBDocumentEvent).where(KBDocumentEvent.document_id == document.id)
            )
        ).all()
    )
    assert [event.event_type for event in events] == ["ingestion.failed"]


@pytest.mark.asyncio
async def test_outbox_worker_is_idempotent_for_already_linked_resource(
    db_session,
    test_settings,
) -> None:
    organization, _admin, document = await _admin_document(db_session)
    linked_id = uuid4()
    await KBDocumentRepository(db_session).link_kb_service_document(
        document,
        kb_service_document_id=linked_id,
    )
    row = await KBIngestOutboxRepository(db_session).enqueue(
        organization_id=organization.id,
        source_type="admin_upload",
        kb_document_id=document.id,
    )
    kb_provider = FakeWorkerKBProvider()

    result = await KbIngestOutboxService(
        db_session,
        storage=FakeWorkerStorageProvider(),
        kb_provider=kb_provider,
        settings=test_settings,
    ).drain_due(limit=25)

    assert result.dispatched == 1
    await db_session.refresh(row)
    assert row.status == "dispatched"
    assert row.kb_service_document_id == linked_id
    assert kb_provider.requests == []


@pytest.mark.asyncio
async def test_outbox_worker_marks_resource_mismatch_failed(
    db_session,
    test_settings,
) -> None:
    organization, _admin, document = await _admin_document(db_session)
    other_organization = await OrganizationRepository(db_session).create(
        name="Other Athletics",
        slug=f"other-outbox-{uuid4()}",
    )
    row = await KBIngestOutboxRepository(db_session).enqueue(
        organization_id=other_organization.id,
        source_type="admin_upload",
        kb_document_id=document.id,
    )
    kb_provider = FakeWorkerKBProvider()

    result = await KbIngestOutboxService(
        db_session,
        storage=FakeWorkerStorageProvider(),
        kb_provider=kb_provider,
        settings=test_settings,
    ).drain_due(limit=25)

    assert result.failed == 1
    await db_session.refresh(row)
    await db_session.refresh(document)
    assert row.status == "failed"
    assert row.attempt_count == 0
    assert row.failure_metadata["error_type"] == "OutboxResourceMismatchError"
    assert document.processing_status == "failed"
    assert kb_provider.requests == []


@pytest.mark.asyncio
async def test_outbox_worker_schedules_retry_for_conversation_file_failure(
    db_session,
    test_settings,
) -> None:
    organization, _athlete, _conversation, file = await _conversation_file(db_session)
    row = await KBIngestOutboxRepository(db_session).enqueue(
        organization_id=organization.id,
        source_type="conversation_file",
        conversation_file_id=file.id,
    )
    kb_provider = FakeWorkerKBProvider(
        failure=KBConnectionError(
            "KB down for https://storage.example/private.pdf?signature=topsecret"
        )
    )

    result = await KbIngestOutboxService(
        db_session,
        storage=FakeWorkerStorageProvider(),
        kb_provider=kb_provider,
        settings=test_settings,
    ).drain_due(limit=25)

    assert result.retried == 1
    await db_session.refresh(row)
    await db_session.refresh(file)
    assert row.status == "retrying"
    assert row.attempt_count == 1
    assert row.next_attempt_at > datetime.now(UTC)
    assert row.failure_metadata["error_type"] == "KBConnectionError"
    assert row.failure_metadata["retryable"] is True
    assert "topsecret" not in repr(row.failure_metadata)
    assert "https://storage.example" not in repr(row.failure_metadata)
    assert file.extraction_status == "uploaded"
    assert len(kb_provider.requests) == 1


@pytest.mark.asyncio
async def test_outbox_worker_marks_conversation_file_terminal_failure(
    db_session,
    test_settings,
) -> None:
    organization, _athlete, _conversation, file = await _conversation_file(db_session)
    row = await KBIngestOutboxRepository(db_session).enqueue(
        organization_id=organization.id,
        source_type="conversation_file",
        conversation_file_id=file.id,
    )
    kb_provider = FakeWorkerKBProvider(
        failure=KBValidationError(
            "Rejected https://storage.example/private.pdf?signature=topsecret"
        )
    )

    result = await KbIngestOutboxService(
        db_session,
        storage=FakeWorkerStorageProvider(),
        kb_provider=kb_provider,
        settings=test_settings,
    ).drain_due(limit=25)

    assert result.failed == 1
    await db_session.refresh(row)
    await db_session.refresh(file)
    assert row.status == "failed"
    assert row.attempt_count == 1
    assert row.failure_metadata["error_type"] == "KBValidationError"
    assert row.failure_metadata["retryable"] is False
    assert "topsecret" not in repr(row.failure_metadata)
    assert row.error_message == "KB ingestion dispatch failed"
    assert file.extraction_status == "failed"
    assert file.error_message == "KB ingestion dispatch failed"
    assert file.extraction_metadata["source_type"] == "conversation_file"
    assert file.extraction_metadata["dispatch_error_type"] == "KBValidationError"


@pytest.mark.asyncio
async def test_outbox_worker_marks_conversation_file_mismatch_failed_without_dispatch(
    db_session,
    test_settings,
) -> None:
    _organization, _athlete, _conversation, file = await _conversation_file(db_session)
    other_organization = await OrganizationRepository(db_session).create(
        name="Other Athletics",
        slug=f"other-file-outbox-{uuid4()}",
    )
    row = await KBIngestOutboxRepository(db_session).enqueue(
        organization_id=other_organization.id,
        source_type="conversation_file",
        conversation_file_id=file.id,
    )
    kb_provider = FakeWorkerKBProvider()

    result = await KbIngestOutboxService(
        db_session,
        storage=FakeWorkerStorageProvider(),
        kb_provider=kb_provider,
        settings=test_settings,
    ).drain_due(limit=25)

    assert result.failed == 1
    await db_session.refresh(row)
    await db_session.refresh(file)
    assert row.status == "failed"
    assert row.attempt_count == 0
    assert row.failure_metadata["error_type"] == "OutboxResourceMismatchError"
    assert file.extraction_status == "failed"
    assert kb_provider.requests == []
