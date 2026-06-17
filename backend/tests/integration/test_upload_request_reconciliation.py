"""Integration tests for Phase 9F direct-upload reconciliation."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import BinaryIO
from uuid import uuid4

import pytest
from sqlalchemy import select
from sqlalchemy.dialects import postgresql

from app.infrastructure.storage.provider import PresignedPostUpload, StoredObjectMetadata
from app.models.knowledge_base import KBDocumentEvent
from app.repositories.conversations import (
    ConversationFileRepository,
    ConversationRepository,
)
from app.repositories.identity import OrganizationRepository, UserRepository
from app.repositories.knowledge_base import KBDocumentRepository
from app.repositories.uploads import KBIngestOutboxRepository, UploadRequestRepository
from app.services.upload_reconciliation_service import (
    SAFE_UPLOAD_EXPIRED_REASON,
    UploadRequestReconciliationService,
)


class FakeReconciliationStorageProvider:
    """Storage fake that records only safe object cleanup operations."""

    def __init__(self, *, fail_head: bool = False, fail_delete: bool = False) -> None:
        self.objects: set[str] = set()
        self.deletes: list[str] = []
        self.fail_head = fail_head
        self.fail_delete = fail_delete

    async def upload_file(self, key: str, file: BinaryIO, content_type: str) -> str:
        self.objects.add(key)
        return key

    async def download_file(self, key: str) -> bytes:
        return b""

    async def delete_file(self, key: str) -> None:
        if self.fail_delete:
            raise RuntimeError("delete failed for signed_url=https://storage.example/x")
        self.deletes.append(key)
        self.objects.discard(key)

    async def get_presigned_url(
        self,
        key: str,
        expires_in: int = 3600,
        download_filename: str | None = None,
    ) -> str:
        return "https://storage.example/redacted"

    async def create_presigned_post(
        self,
        *,
        key: str,
        content_type: str,
        max_size_bytes: int,
        expires_in: int | None = None,
    ) -> PresignedPostUpload:
        return PresignedPostUpload(
            url="https://storage.example/upload",
            fields={"key": key, "Content-Type": content_type},
            expires_at=datetime.now(UTC) + timedelta(minutes=15),
        )

    async def get_object_metadata(self, key: str) -> StoredObjectMetadata | None:
        if self.fail_head:
            raise RuntimeError("head failed for signed_url=https://storage.example/x")
        if key not in self.objects:
            return None
        return StoredObjectMetadata(
            key=key,
            content_length=10,
            content_type="application/pdf",
        )

    async def file_exists(self, key: str) -> bool:
        return key in self.objects


def test_expired_pending_request_statement_can_lock_and_skip_locked() -> None:
    stmt = UploadRequestRepository.expired_pending_requests_statement(
        now=datetime.now(UTC),
        limit=10,
        for_update=True,
    )

    compiled = str(stmt.compile(dialect=postgresql.dialect()))

    assert "FOR UPDATE SKIP LOCKED" in compiled


@pytest.mark.asyncio
async def test_reconciliation_expires_admin_upload_and_deletes_known_object(
    db_session,
) -> None:
    organization = await OrganizationRepository(db_session).create(
        name="Playbook Athletics",
        slug=f"playbook-reconcile-admin-{uuid4()}",
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
        size_bytes=10,
        storage_key=f"kb/originals/{organization.id}/nil-handbook.pdf",
        processing_status="upload_pending",
    )
    request = await UploadRequestRepository(db_session).create(
        organization_id=organization.id,
        requested_by=admin.id,
        source_type="admin_upload",
        filename=document.filename,
        content_type=document.content_type,
        size_bytes=document.size_bytes,
        storage_key=document.storage_key,
        expires_at=datetime.now(UTC) - timedelta(minutes=1),
        kb_document_id=document.id,
    )
    storage = FakeReconciliationStorageProvider()
    storage.objects.add(document.storage_key)

    result = await UploadRequestReconciliationService(
        db_session,
        storage=storage,
    ).reconcile_expired(limit=10)

    await db_session.refresh(request)
    await db_session.refresh(document)
    events = list(
        (
            await db_session.scalars(
                select(KBDocumentEvent).where(KBDocumentEvent.document_id == document.id)
            )
        ).all()
    )

    assert result.processed == 1
    assert result.expired == 1
    assert result.resources_failed == 1
    assert result.objects_deleted == 1
    assert storage.deletes == [document.storage_key]
    assert request.status == "expired"
    assert request.request_metadata["failure_code"] == "upload_request_expired"
    assert request.request_metadata["cleanup_status"] == "deleted"
    assert document.processing_status == "failed"
    assert document.failure_reason == SAFE_UPLOAD_EXPIRED_REASON
    assert [event.event_type for event in events] == ["document.upload_expired"]
    assert events[0].message == SAFE_UPLOAD_EXPIRED_REASON
    assert document.storage_key not in repr(request.request_metadata)
    assert document.storage_key not in repr(events[0].event_metadata)


@pytest.mark.asyncio
async def test_reconciliation_expires_conversation_file_with_missing_object(
    db_session,
) -> None:
    organization = await OrganizationRepository(db_session).create(
        name="Playbook Athletics",
        slug=f"playbook-reconcile-file-{uuid4()}",
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
        filename="contract.pdf",
        content_type="application/pdf",
        size_bytes=10,
        storage_key=f"conversation-files/originals/{organization.id}/contract.pdf",
        extraction_status="upload_pending",
    )
    request = await UploadRequestRepository(db_session).create(
        organization_id=organization.id,
        requested_by=athlete.id,
        source_type="conversation_file",
        filename=file.filename,
        content_type=file.content_type,
        size_bytes=file.size_bytes,
        storage_key=file.storage_key,
        expires_at=datetime.now(UTC) - timedelta(minutes=1),
        conversation_file_id=file.id,
    )
    storage = FakeReconciliationStorageProvider()

    result = await UploadRequestReconciliationService(
        db_session,
        storage=storage,
    ).reconcile_expired(limit=10)

    await db_session.refresh(request)
    await db_session.refresh(file)

    assert result.processed == 1
    assert result.expired == 1
    assert result.resources_failed == 1
    assert result.objects_missing == 1
    assert storage.deletes == []
    assert request.status == "expired"
    assert request.request_metadata["cleanup_status"] == "missing"
    assert file.extraction_status == "failed"
    assert file.error_message == SAFE_UPLOAD_EXPIRED_REASON
    assert file.extraction_metadata["failure_code"] == "upload_request_expired"
    assert file.extraction_metadata["upload_request_id"] == str(request.id)
    assert file.storage_key not in repr(file.extraction_metadata)


@pytest.mark.asyncio
async def test_reconciliation_is_idempotent_and_skips_transitioned_resources(
    db_session,
) -> None:
    organization = await OrganizationRepository(db_session).create(
        name="Playbook Athletics",
        slug=f"playbook-reconcile-skip-{uuid4()}",
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
        filename="ready.pdf",
        content_type="application/pdf",
        size_bytes=10,
        storage_key=f"conversation-files/originals/{organization.id}/ready.pdf",
        extraction_status="ready",
    )
    request = await UploadRequestRepository(db_session).create(
        organization_id=organization.id,
        requested_by=athlete.id,
        source_type="conversation_file",
        filename=file.filename,
        content_type=file.content_type,
        size_bytes=file.size_bytes,
        storage_key=file.storage_key,
        expires_at=datetime.now(UTC) - timedelta(minutes=1),
        conversation_file_id=file.id,
    )
    storage = FakeReconciliationStorageProvider()
    storage.objects.add(file.storage_key)
    service = UploadRequestReconciliationService(db_session, storage=storage)

    first = await service.reconcile_expired(limit=10)
    second = await service.reconcile_expired(limit=10)

    await db_session.refresh(request)
    await db_session.refresh(file)

    assert first.processed == 1
    assert first.skipped == 1
    assert first.objects_deleted == 0
    assert second.processed == 0
    assert storage.deletes == []
    assert request.status == "expired"
    assert file.extraction_status == "ready"
    assert request.request_metadata["failure_code"] == "resource_already_transitioned"
    assert request.request_metadata["resource_status"] == "ready"


@pytest.mark.asyncio
async def test_reconciliation_reports_cleanup_failure_without_sensitive_metadata(
    db_session,
) -> None:
    organization = await OrganizationRepository(db_session).create(
        name="Playbook Athletics",
        slug=f"playbook-reconcile-cleanup-fail-{uuid4()}",
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
        filename="cleanup.pdf",
        content_type="application/pdf",
        size_bytes=10,
        storage_key=f"conversation-files/originals/{organization.id}/cleanup.pdf",
        extraction_status="upload_pending",
    )
    request = await UploadRequestRepository(db_session).create(
        organization_id=organization.id,
        requested_by=athlete.id,
        source_type="conversation_file",
        filename=file.filename,
        content_type=file.content_type,
        size_bytes=file.size_bytes,
        storage_key=file.storage_key,
        expires_at=datetime.now(UTC) - timedelta(minutes=1),
        conversation_file_id=file.id,
    )
    storage = FakeReconciliationStorageProvider(fail_delete=True)
    storage.objects.add(file.storage_key)

    result = await UploadRequestReconciliationService(
        db_session,
        storage=storage,
    ).reconcile_expired(limit=10)

    await db_session.refresh(request)
    await db_session.refresh(file)

    payload = result.to_task_payload()
    assert result.cleanup_failed == 1
    assert request.status == "expired"
    assert file.extraction_status == "failed"
    assert request.request_metadata["cleanup_status"] == "failed"
    assert file.storage_key not in repr(payload)
    assert "signed_url" not in repr(payload)


@pytest.mark.asyncio
async def test_reconciliation_reports_outbox_backlog_and_next_expiration(
    db_session,
) -> None:
    organization = await OrganizationRepository(db_session).create(
        name="Playbook Athletics",
        slug=f"playbook-reconcile-backlog-{uuid4()}",
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
        title="Future",
        filename="future.pdf",
        content_type="application/pdf",
        size_bytes=10,
        storage_key=f"kb/originals/{organization.id}/future.pdf",
        processing_status="upload_pending",
    )
    future_expiration = datetime.now(UTC) + timedelta(minutes=10)
    await UploadRequestRepository(db_session).create(
        organization_id=organization.id,
        requested_by=admin.id,
        source_type="admin_upload",
        filename=document.filename,
        content_type=document.content_type,
        size_bytes=document.size_bytes,
        storage_key=document.storage_key,
        expires_at=future_expiration,
        kb_document_id=document.id,
    )
    await KBIngestOutboxRepository(db_session).enqueue(
        organization_id=organization.id,
        source_type="admin_upload",
        kb_document_id=document.id,
    )

    result = await UploadRequestReconciliationService(
        db_session,
        storage=FakeReconciliationStorageProvider(),
    ).reconcile_expired(limit=10)

    assert result.processed == 0
    assert result.admin_upload_pending_count == 1
    assert result.conversation_upload_pending_count == 0
    assert result.outbox_due_backlog == 1
    assert result.next_expiration_at == future_expiration
    assert result.next_countdown_seconds() is not None
