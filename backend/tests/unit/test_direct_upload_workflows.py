"""Unit tests for shared direct-upload workflow helpers."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import UUID, uuid4

import pytest

from app.core.exceptions import StorageError, ValidationError
from app.infrastructure.storage.provider import (
    ObjectVerificationResult,
    PresignedPostUpload,
)
from app.services.direct_uploads import DirectUploadSourceRef, DirectUploadWorkflow
from app.services.upload_validation import (
    raise_for_upload_verification_failure,
    validate_kb_metadata_tags,
)


@dataclass
class _UploadRequestStub:
    id: UUID
    organization_id: UUID
    source_type: str
    filename: str
    content_type: str
    size_bytes: int
    storage_key: str
    expires_at: datetime
    requested_by: UUID | None = None
    status: str = "pending"
    completed_at: datetime | None = None
    kb_document_id: UUID | None = None
    conversation_file_id: UUID | None = None
    request_metadata: dict[str, Any] | None = None


class _StorageStub:
    def __init__(
        self,
        *,
        presign_error: Exception | None = None,
        verification_status: str = "valid",
    ) -> None:
        self.presign_error = presign_error
        self.verification_status = verification_status
        self.presigned_posts: list[tuple[str, str, int]] = []
        self.verified_keys: list[str] = []

    async def create_presigned_post(
        self,
        *,
        key: str,
        content_type: str,
        max_size_bytes: int,
        expires_in: int | None = None,
    ) -> PresignedPostUpload:
        if self.presign_error is not None:
            raise self.presign_error
        self.presigned_posts.append((key, content_type, max_size_bytes))
        return PresignedPostUpload(
            url="https://storage.example/upload",
            fields={"key": key, "Content-Type": content_type},
            expires_at=datetime.now(UTC) + timedelta(minutes=15),
        )

    async def verify_object(
        self,
        *,
        key: str,
        expected_size_bytes: int,
        expected_content_type: str,
    ) -> ObjectVerificationResult:
        self.verified_keys.append(key)
        return ObjectVerificationResult(status=self.verification_status)  # type: ignore[arg-type]


class _UploadRequestRepoStub:
    def __init__(self) -> None:
        self.created: list[dict[str, Any]] = []
        self.completed: list[_UploadRequestStub] = []

    async def create(self, **kwargs: Any) -> _UploadRequestStub:
        self.created.append(kwargs)
        return _UploadRequestStub(id=uuid4(), **kwargs)

    async def mark_completed(
        self,
        request: _UploadRequestStub,
        *,
        completed_at: datetime | None = None,
    ) -> _UploadRequestStub:
        request.status = "completed"
        request.completed_at = completed_at or datetime.now(UTC)
        self.completed.append(request)
        return request


class _OutboxRepoStub:
    def __init__(self) -> None:
        self.enqueued: list[dict[str, Any]] = []

    async def enqueue(self, **kwargs: Any) -> object:
        self.enqueued.append(kwargs)
        return object()


class _DispatcherStub:
    def __init__(self) -> None:
        self.calls: list[dict[str, Any]] = []

    def dispatch(self, **kwargs: Any) -> str:
        self.calls.append(kwargs)
        return "task-id"


def test_direct_upload_source_ref_enforces_exactly_one_resource() -> None:
    document_id = uuid4()
    file_id = uuid4()

    assert DirectUploadSourceRef.admin_document(document_id).source_type == "admin_upload"
    assert (
        DirectUploadSourceRef.conversation_file(file_id).source_type
        == "conversation_file"
    )

    with pytest.raises(ValueError):
        DirectUploadSourceRef(source_type="admin_upload")

    with pytest.raises(ValueError):
        DirectUploadSourceRef(
            source_type="admin_upload",
            kb_document_id=document_id,
            conversation_file_id=file_id,
        )


def test_validate_kb_metadata_tags_rejects_reserved_client_keys() -> None:
    with pytest.raises(ValidationError) as exc_info:
        validate_kb_metadata_tags({"topic": "nil", "source_type": "admin_upload"})

    assert exc_info.value.message == "metadata_tags contains reserved keys: source_type"


@pytest.mark.asyncio
async def test_create_presigned_post_wraps_storage_errors_safely() -> None:
    storage = _StorageStub(
        presign_error=RuntimeError("signed_url=https://storage.example/secret")
    )
    workflow = DirectUploadWorkflow(
        storage=storage,  # type: ignore[arg-type]
        upload_request_repo=_UploadRequestRepoStub(),  # type: ignore[arg-type]
        outbox_repo=_OutboxRepoStub(),  # type: ignore[arg-type]
        outbox_dispatcher=_DispatcherStub(),  # type: ignore[arg-type]
        upload_reconciliation_dispatcher=_DispatcherStub(),  # type: ignore[arg-type]
    )

    with pytest.raises(StorageError) as exc_info:
        await workflow.create_presigned_post(
            storage_key="kb/originals/document.pdf",
            content_type="application/pdf",
            size_bytes=10,
            error_message="KB document upload request failed",
            log_event="kb_document_presign_failed",
            log_context={"document_id": str(uuid4())},
        )

    assert exc_info.value.message == "KB document upload request failed"
    assert "storage.example" not in repr(exc_info.value.details)


@pytest.mark.asyncio
async def test_record_upload_request_uses_trusted_resource_reference() -> None:
    organization_id = uuid4()
    document_id = uuid4()
    expires_at = datetime.now(UTC) + timedelta(minutes=15)
    upload_repo = _UploadRequestRepoStub()
    workflow = DirectUploadWorkflow(
        storage=_StorageStub(),  # type: ignore[arg-type]
        upload_request_repo=upload_repo,  # type: ignore[arg-type]
        outbox_repo=_OutboxRepoStub(),  # type: ignore[arg-type]
        outbox_dispatcher=_DispatcherStub(),  # type: ignore[arg-type]
        upload_reconciliation_dispatcher=_DispatcherStub(),  # type: ignore[arg-type]
    )

    request = await workflow.record_upload_request(
        organization_id=organization_id,
        requested_by=uuid4(),
        source=DirectUploadSourceRef.admin_document(document_id),
        filename="nil-handbook.pdf",
        content_type="application/pdf",
        size_bytes=10,
        storage_key="kb/originals/document.pdf",
        expires_at=expires_at,
    )

    assert request.kb_document_id == document_id
    assert request.conversation_file_id is None
    assert upload_repo.created[0]["source_type"] == "admin_upload"


@pytest.mark.asyncio
async def test_complete_upload_request_is_idempotent_for_completed_request() -> None:
    storage = _StorageStub()
    upload_repo = _UploadRequestRepoStub()
    workflow = DirectUploadWorkflow(
        storage=storage,  # type: ignore[arg-type]
        upload_request_repo=upload_repo,  # type: ignore[arg-type]
        outbox_repo=_OutboxRepoStub(),  # type: ignore[arg-type]
        outbox_dispatcher=_DispatcherStub(),  # type: ignore[arg-type]
        upload_reconciliation_dispatcher=_DispatcherStub(),  # type: ignore[arg-type]
    )
    request = _UploadRequestStub(
        id=uuid4(),
        organization_id=uuid4(),
        source_type="conversation_file",
        filename="contract.pdf",
        content_type="application/pdf",
        size_bytes=10,
        storage_key="conversation-files/originals/contract.pdf",
        expires_at=datetime.now(UTC) + timedelta(minutes=15),
        status="completed",
        conversation_file_id=uuid4(),
    )

    result = await workflow.complete_upload_request(request)  # type: ignore[arg-type]

    assert result.status == "already_completed"
    assert storage.verified_keys == []
    assert upload_repo.completed == []


@pytest.mark.asyncio
async def test_complete_upload_request_verifies_and_marks_pending_request() -> None:
    storage = _StorageStub(verification_status="valid")
    upload_repo = _UploadRequestRepoStub()
    workflow = DirectUploadWorkflow(
        storage=storage,  # type: ignore[arg-type]
        upload_request_repo=upload_repo,  # type: ignore[arg-type]
        outbox_repo=_OutboxRepoStub(),  # type: ignore[arg-type]
        outbox_dispatcher=_DispatcherStub(),  # type: ignore[arg-type]
        upload_reconciliation_dispatcher=_DispatcherStub(),  # type: ignore[arg-type]
    )
    request = _UploadRequestStub(
        id=uuid4(),
        organization_id=uuid4(),
        source_type="admin_upload",
        filename="nil.pdf",
        content_type="application/pdf",
        size_bytes=10,
        storage_key="kb/originals/nil.pdf",
        expires_at=datetime.now(UTC) + timedelta(minutes=15),
        kb_document_id=uuid4(),
    )

    result = await workflow.complete_upload_request(request)  # type: ignore[arg-type]

    assert result.status == "completed"
    assert storage.verified_keys == [request.storage_key]
    assert upload_repo.completed == [request]


def test_upload_verification_errors_keep_existing_messages() -> None:
    with pytest.raises(ValidationError) as missing:
        raise_for_upload_verification_failure("missing")

    with pytest.raises(ValidationError) as mismatch:
        raise_for_upload_verification_failure("content_type_mismatch")

    assert missing.value.message == "Uploaded object is missing"
    assert mismatch.value.message == "Uploaded object does not match request metadata"


@pytest.mark.asyncio
async def test_enqueue_ingest_and_dispatch_helpers_use_existing_dispatchers() -> None:
    outbox_repo = _OutboxRepoStub()
    outbox_dispatcher = _DispatcherStub()
    reconciliation_dispatcher = _DispatcherStub()
    workflow = DirectUploadWorkflow(
        storage=_StorageStub(),  # type: ignore[arg-type]
        upload_request_repo=_UploadRequestRepoStub(),  # type: ignore[arg-type]
        outbox_repo=outbox_repo,  # type: ignore[arg-type]
        outbox_dispatcher=outbox_dispatcher,  # type: ignore[arg-type]
        upload_reconciliation_dispatcher=reconciliation_dispatcher,  # type: ignore[arg-type]
    )
    file_id = uuid4()
    organization_id = uuid4()

    await workflow.enqueue_ingest(
        organization_id=organization_id,
        source=DirectUploadSourceRef.conversation_file(file_id),
    )
    workflow.dispatch_kb_ingest_outbox(
        log_context={"conversation_file_id": str(file_id)}
    )
    workflow.dispatch_upload_reconciliation(
        expires_at=datetime.now(UTC) + timedelta(seconds=30),
        log_context={"conversation_file_id": str(file_id)},
    )

    assert outbox_repo.enqueued == [
        {
            "organization_id": organization_id,
            "source_type": "conversation_file",
            "kb_document_id": None,
            "conversation_file_id": file_id,
        }
    ]
    assert outbox_dispatcher.calls == [{}]
    assert reconciliation_dispatcher.calls[0]["countdown"] >= 0
