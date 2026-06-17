"""Integration tests for direct-upload request repositories."""

from datetime import UTC, datetime, timedelta

import pytest

from app.repositories.conversations import ConversationFileRepository, ConversationRepository
from app.repositories.identity import OrganizationRepository, UserRepository
from app.repositories.knowledge_base import KBDocumentRepository
from app.repositories.uploads import UploadRequestRepository


@pytest.mark.asyncio
async def test_upload_request_repository_manages_admin_upload_request(db_session):
    organization = await OrganizationRepository(db_session).create(
        name="Playbook Athletics",
        slug="playbook-upload-request-admin",
    )
    admin = await UserRepository(db_session).create(
        organization_id=organization.id,
        email="admin-upload-request@example.com",
        name="Admin User",
        auth_provider="google",
        provider_subject="admin-upload-request",
        role="admin",
    )
    document = await KBDocumentRepository(db_session).create(
        organization_id=organization.id,
        uploaded_by=admin.id,
        title="NIL Handbook",
        filename="nil-handbook.pdf",
        content_type="application/pdf",
        size_bytes=12345,
        storage_key="kb/originals/document/nil-handbook.pdf",
    )
    repository = UploadRequestRepository(db_session)
    expires_at = datetime.now(UTC) + timedelta(minutes=15)

    request = await repository.create(
        organization_id=organization.id,
        requested_by=admin.id,
        source_type="admin_upload",
        filename=document.filename,
        content_type=document.content_type,
        size_bytes=document.size_bytes,
        storage_key=document.storage_key,
        expires_at=expires_at,
        kb_document_id=document.id,
        request_metadata={"route": "admin"},
    )

    assert request.status == "pending"
    assert request.request_metadata == {"route": "admin"}

    by_id = await repository.get(request.id)
    by_resource = await repository.get_for_admin_document(
        upload_request_id=request.id,
        document_id=document.id,
    )
    await repository.mark_completed(request)

    assert by_id is request
    assert by_resource is request
    assert request.status == "completed"
    assert request.completed_at is not None


@pytest.mark.asyncio
async def test_upload_request_repository_lists_and_expires_pending_requests(
    db_session,
):
    organization = await OrganizationRepository(db_session).create(
        name="Playbook Athletics",
        slug="playbook-upload-request-file",
    )
    athlete = await UserRepository(db_session).create(
        organization_id=organization.id,
        email="athlete-upload-request@example.com",
        name="Jordan Athlete",
        auth_provider="google",
        provider_subject="athlete-upload-request",
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
        extraction_status="upload_pending",
    )
    repository = UploadRequestRepository(db_session)
    now = datetime.now(UTC)
    request = await repository.create(
        organization_id=organization.id,
        requested_by=athlete.id,
        source_type="conversation_file",
        filename=file.filename,
        content_type=file.content_type,
        size_bytes=file.size_bytes,
        storage_key=file.storage_key,
        expires_at=now - timedelta(minutes=1),
        conversation_file_id=file.id,
    )
    fresh_request = await repository.create(
        organization_id=organization.id,
        requested_by=athlete.id,
        source_type="conversation_file",
        filename=file.filename,
        content_type=file.content_type,
        size_bytes=file.size_bytes,
        storage_key="conversation-files/originals/fresh.pdf",
        expires_at=now + timedelta(minutes=10),
        conversation_file_id=file.id,
    )

    expired = await repository.list_expired_pending_requests(now=now)
    by_resource = await repository.get_for_conversation_file(
        upload_request_id=request.id,
        conversation_file_id=file.id,
    )
    await repository.mark_expired(request)
    await repository.mark_failed(fresh_request, metadata={"reason": "storage_failed"})

    assert expired == [request]
    assert by_resource is request
    assert request.status == "expired"
    assert fresh_request.status == "failed"
    assert fresh_request.request_metadata == {"reason": "storage_failed"}
