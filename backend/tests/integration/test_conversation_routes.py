"""Route-level tests for athlete conversation endpoints."""

from __future__ import annotations

from types import SimpleNamespace
from typing import BinaryIO
from uuid import UUID, uuid4

import pytest

from app.api.v1.dependencies import get_agent_stream_service
from app.infrastructure.knowledgebase import get_kb_provider_dependency
from app.infrastructure.storage import get_storage_provider_dependency
from app.infrastructure.streaming import InMemoryAgentStreamProvider
from app.repositories.conversations import (
    ConversationFileRepository,
    ConversationMessageRepository,
    ConversationRepository,
    MessageCitationRepository,
)
from app.repositories.identity import OrganizationRepository, UserRepository
from app.schemas.knowledgebase import (
    KBConversationFileIngestRequest,
    KBDocumentIngestResponse,
)
from app.services.agent_stream_service import AgentStreamService
from app.workers import tasks as worker_tasks


class FakeStorageProvider:
    """Storage fake that records upload and presign operations."""

    def __init__(self, *, fail_upload: bool = False, fail_presign: bool = False) -> None:
        self.uploads: list[tuple[str, str, int]] = []
        self.presigned: list[tuple[str, str | None]] = []
        self.fail_upload = fail_upload
        self.fail_presign = fail_presign

    async def upload_file(self, key: str, file: BinaryIO, content_type: str) -> str:
        if self.fail_upload:
            raise RuntimeError(
                "upload failed for https://storage.example/private.pdf?signature=secret"
            )
        data = file.read()
        file.seek(0)
        self.uploads.append((key, content_type, len(data)))
        return key

    async def download_file(self, key: str) -> bytes:
        return b"document"

    async def delete_file(self, key: str) -> None:
        return None

    async def get_presigned_url(
        self,
        key: str,
        expires_in: int = 3600,
        download_filename: str | None = None,
    ) -> str:
        if self.fail_presign:
            raise RuntimeError(
                "presign failed for https://storage.example/private.pdf?signature=secret"
            )
        self.presigned.append((key, download_filename))
        return f"https://storage.example/{key}?filename={download_filename}"

    async def file_exists(self, key: str) -> bool:
        return True


class FakeConversationFileIngestProvider:
    """Recorder for trusted conversation-file ingest requests."""

    def __init__(self, *, fail: bool = False) -> None:
        self.requests: list[KBConversationFileIngestRequest] = []
        self.fail = fail

    async def ingest_source(
        self,
        request: KBConversationFileIngestRequest,
    ) -> KBDocumentIngestResponse:
        self.requests.append(request)
        if self.fail:
            raise RuntimeError("signed URL expired: https://storage.example/secret")
        return KBDocumentIngestResponse(
            kb_service_document_id=uuid4(),
            source_type="conversation_file",
            conversation_id=request.conversation_id,
            conversation_file_id=request.conversation_file_id,
            task_id="kb-file-task-1",
            status="pending",
        )


def _override_file_upload_dependencies(
    route_client,
    *,
    fail_dispatch: bool = False,
    fail_storage_upload: bool = False,
    fail_storage_presign: bool = False,
):
    storage = FakeStorageProvider(
        fail_upload=fail_storage_upload,
        fail_presign=fail_storage_presign,
    )
    kb_provider = FakeConversationFileIngestProvider(fail=fail_dispatch)
    route_client.app.dependency_overrides[get_storage_provider_dependency] = (
        lambda: storage
    )
    route_client.app.dependency_overrides[get_kb_provider_dependency] = (
        lambda: kb_provider
    )
    return storage, kb_provider


@pytest.mark.asyncio
async def test_athlete_conversation_routes_create_list_and_get_detail(
    route_client,
    db_session,
) -> None:
    organization = await OrganizationRepository(db_session).create(
        name="Playbook Athletics",
        slug="playbook",
    )
    athlete = await UserRepository(db_session).create(
        organization_id=organization.id,
        email="athlete@example.com",
        name="Jordan Athlete",
        auth_provider="google",
        provider_subject="athlete-subject",
        sport_team="Basketball",
    )
    route_client.authenticate_as(athlete)

    create_response = await route_client.client.post(
        "/api/v1/conversations",
        json={"initial_message": " Can I accept this NIL deal? "},
    )

    assert create_response.status_code == 201
    conversation_id = create_response.json()["id"]
    conversation_uuid = UUID(conversation_id)
    assert create_response.json()["athlete_id"] == str(athlete.id)
    assert create_response.json()["title"] is None
    assert create_response.json()["last_message_at"] is not None
    assert create_response.json()["messages"][0]["role"] == "user"
    assert create_response.json()["messages"][0]["content"] == (
        "Can I accept this NIL deal?"
    )
    assert create_response.json()["files"] == []

    message = await ConversationMessageRepository(db_session).create(
        conversation_id=conversation_uuid,
        role="assistant",
        content="Check the NIL handbook.",
        topic_labels=["nil"],
    )
    citation = await MessageCitationRepository(db_session).create(
        message_id=message.id,
        source_title="NIL Handbook",
        rank=1,
    )
    file = await ConversationFileRepository(db_session).create(
        conversation_id=conversation_uuid,
        uploaded_by=athlete.id,
        filename="nil-contract.pdf",
        content_type="application/pdf",
        size_bytes=123456,
        storage_key="conversations/org/conversation/file/nil-contract.pdf",
        message_id=message.id,
    )
    list_response = await route_client.client.get("/api/v1/conversations")
    detail_response = await route_client.client.get(
        f"/api/v1/conversations/{conversation_id}"
    )

    assert list_response.status_code == 200
    assert [row["id"] for row in list_response.json()] == [conversation_id]
    assert list_response.json()[0]["title"] is None
    assert list_response.json()[0]["last_message_at"] is not None
    assert detail_response.status_code == 200
    assert detail_response.json()["messages"][0]["role"] == "user"
    assert detail_response.json()["messages"][1]["id"] == str(message.id)
    assert detail_response.json()["messages"][1]["citations"][0]["id"] == str(
        citation.id
    )
    assert detail_response.json()["files"] == [
        {
            "id": str(file.id),
            "conversation_id": conversation_id,
            "message_id": str(message.id),
            "filename": "nil-contract.pdf",
            "content_type": "application/pdf",
            "size_bytes": 123456,
            "extraction_status": "uploaded",
            "chunk_count": 0,
            "created_at": file.created_at.isoformat().replace("+00:00", "Z"),
            "updated_at": file.updated_at.isoformat().replace("+00:00", "Z"),
        }
    ]
    assert "storage_key" not in detail_response.json()["files"][0]
    assert "extracted_text_ref" not in detail_response.json()["files"][0]


@pytest.mark.asyncio
async def test_upload_conversation_file_stores_metadata_and_dispatches_private_ingest(
    route_client,
    db_session,
) -> None:
    organization = await OrganizationRepository(db_session).create(
        name="Playbook Athletics",
        slug="playbook",
    )
    athlete = await UserRepository(db_session).create(
        organization_id=organization.id,
        email="athlete@example.com",
        name="Jordan Athlete",
        auth_provider="google",
        provider_subject="athlete-upload-subject",
        sport_team="Basketball",
    )
    conversation = await ConversationRepository(db_session).create(
        organization_id=organization.id,
        athlete_id=athlete.id,
    )
    route_client.authenticate_as(athlete)
    storage, kb_provider = _override_file_upload_dependencies(route_client)

    response = await route_client.client.post(
        f"/api/v1/conversations/{conversation.id}/files",
        files={
            "file": (
                "nil-contract.pdf",
                b"%PDF-1.7 contract",
                "application/pdf",
            )
        },
    )

    assert response.status_code == 201
    body = response.json()
    file_id = UUID(body["id"])
    assert body["conversation_id"] == str(conversation.id)
    assert body["message_id"] is None
    assert body["filename"] == "nil-contract.pdf"
    assert body["content_type"] == "application/pdf"
    assert body["size_bytes"] == len(b"%PDF-1.7 contract")
    assert body["extraction_status"] == "extracting"
    assert body["chunk_count"] == 0
    assert "storage_key" not in body
    assert "source_uri" not in body
    assert "extracted_text_ref" not in body

    assert len(storage.uploads) == 1
    storage_key, content_type, size_bytes = storage.uploads[0]
    assert storage_key.startswith(
        f"conversation-files/originals/{organization.id}/{conversation.id}/{file_id}/"
    )
    assert storage_key.endswith("/nil-contract.pdf")
    assert content_type == "application/pdf"
    assert size_bytes == len(b"%PDF-1.7 contract")
    assert storage.presigned == [(storage_key, "nil-contract.pdf")]

    persisted = await ConversationFileRepository(db_session).list_by_conversation_and_ids(
        conversation.id,
        [file_id],
    )
    assert persisted[0].storage_key == storage_key
    assert persisted[0].extraction_status == "extracting"
    assert persisted[0].extraction_metadata["source_type"] == "conversation_file"
    assert persisted[0].extraction_metadata["conversation_id"] == str(conversation.id)
    assert persisted[0].extraction_metadata["conversation_file_id"] == str(file_id)
    assert persisted[0].extraction_metadata["task_id"] == "kb-file-task-1"
    assert "kb_service_document_id" in persisted[0].extraction_metadata
    assert "source_uri" not in persisted[0].extraction_metadata

    assert len(kb_provider.requests) == 1
    request = kb_provider.requests[0]
    assert request.source_type == "conversation_file"
    assert request.organization_id == organization.id
    assert request.conversation_id == conversation.id
    assert request.conversation_file_id == file_id
    assert request.filename == "nil-contract.pdf"
    assert request.source_title == "nil-contract.pdf"
    assert request.visibility_policy == {"scope": "conversation"}
    assert request.source_uri.startswith("https://storage.example/")
    assert "signature" not in response.text

    detail_response = await route_client.client.get(
        f"/api/v1/conversations/{conversation.id}"
    )

    assert detail_response.status_code == 200
    assert detail_response.json()["files"][0]["id"] == str(file_id)
    assert detail_response.json()["files"][0]["extraction_status"] == "extracting"
    assert detail_response.json()["files"][0]["chunk_count"] == 0
    assert "storage_key" not in detail_response.json()["files"][0]
    assert "source_uri" not in detail_response.json()["files"][0]


@pytest.mark.asyncio
async def test_upload_conversation_file_marks_failed_when_kb_dispatch_fails(
    route_client,
    db_session,
) -> None:
    organization = await OrganizationRepository(db_session).create(
        name="Playbook Athletics",
        slug="playbook",
    )
    athlete = await UserRepository(db_session).create(
        organization_id=organization.id,
        email="athlete-fail@example.com",
        name="Jordan Athlete",
        auth_provider="google",
        provider_subject="athlete-upload-fail-subject",
    )
    conversation = await ConversationRepository(db_session).create(
        organization_id=organization.id,
        athlete_id=athlete.id,
    )
    route_client.authenticate_as(athlete)
    _storage, kb_provider = _override_file_upload_dependencies(
        route_client,
        fail_dispatch=True,
    )

    response = await route_client.client.post(
        f"/api/v1/conversations/{conversation.id}/files",
        files={
            "file": (
                "nil-contract.pdf",
                b"%PDF-1.7 contract",
                "application/pdf",
            )
        },
    )

    assert response.status_code == 201
    body = response.json()
    file_id = UUID(body["id"])
    assert body["extraction_status"] == "failed"
    assert "signed URL" not in response.text
    assert "storage.example" not in response.text

    persisted = await ConversationFileRepository(db_session).list_by_conversation_and_ids(
        conversation.id,
        [file_id],
    )
    assert persisted[0].extraction_status == "failed"
    assert persisted[0].extraction_metadata["source_type"] == "conversation_file"
    assert persisted[0].extraction_metadata["dispatch_error_type"] == "RuntimeError"
    assert "storage.example" not in str(persisted[0].extraction_metadata)
    assert "storage.example" not in (persisted[0].error_message or "")
    assert len(kb_provider.requests) == 1


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("fail_storage_upload", "fail_storage_presign"),
    [(True, False), (False, True)],
)
async def test_upload_conversation_file_storage_failure_is_sanitized_and_not_persisted(
    route_client,
    db_session,
    fail_storage_upload: bool,
    fail_storage_presign: bool,
) -> None:
    organization = await OrganizationRepository(db_session).create(
        name="Playbook Athletics",
        slug=f"playbook-storage-failure-{fail_storage_upload}-{fail_storage_presign}",
    )
    athlete = await UserRepository(db_session).create(
        organization_id=organization.id,
        email=f"athlete-storage-{fail_storage_upload}-{fail_storage_presign}@example.com",
        name="Jordan Athlete",
        auth_provider="google",
        provider_subject=f"athlete-storage-{fail_storage_upload}-{fail_storage_presign}",
    )
    conversation = await ConversationRepository(db_session).create(
        organization_id=organization.id,
        athlete_id=athlete.id,
    )
    route_client.authenticate_as(athlete)
    storage, kb_provider = _override_file_upload_dependencies(
        route_client,
        fail_storage_upload=fail_storage_upload,
        fail_storage_presign=fail_storage_presign,
    )

    response = await route_client.client.post(
        f"/api/v1/conversations/{conversation.id}/files",
        files={
            "file": (
                "nil-contract.pdf",
                b"%PDF-1.7 contract",
                "application/pdf",
            )
        },
        headers={"X-Request-ID": "req-storage-failure"},
    )

    assert response.status_code == 500
    assert response.json()["error"] == {
        "code": "STORAGE_ERROR",
        "message": "Conversation file storage failed",
        "retryable": True,
        "details": {"request_id": "req-storage-failure"},
    }
    assert "storage.example" not in response.text
    assert "signature=secret" not in response.text
    assert kb_provider.requests == []

    files = await ConversationFileRepository(
        db_session
    ).list_by_conversation_with_chunk_counts(conversation.id)
    assert files == []
    if fail_storage_upload:
        assert storage.uploads == []
        assert storage.presigned == []
    else:
        assert len(storage.uploads) == 1
        assert storage.presigned == []


@pytest.mark.asyncio
async def test_upload_conversation_file_is_scoped_to_current_athlete(
    route_client,
    db_session,
) -> None:
    organization = await OrganizationRepository(db_session).create(
        name="Playbook Athletics",
        slug="playbook",
    )
    user_repo = UserRepository(db_session)
    owner = await user_repo.create(
        organization_id=organization.id,
        email="owner@example.com",
        name="Owner Athlete",
        auth_provider="google",
        provider_subject="owner-upload-subject",
    )
    other = await user_repo.create(
        organization_id=organization.id,
        email="other@example.com",
        name="Other Athlete",
        auth_provider="google",
        provider_subject="other-upload-subject",
    )
    conversation = await ConversationRepository(db_session).create(
        organization_id=organization.id,
        athlete_id=owner.id,
    )
    route_client.authenticate_as(other)
    storage, kb_provider = _override_file_upload_dependencies(route_client)

    response = await route_client.client.post(
        f"/api/v1/conversations/{conversation.id}/files",
        files={"file": ("contract.pdf", b"%PDF-1.7", "application/pdf")},
        headers={"X-Request-ID": "req-upload-owner"},
    )

    assert response.status_code == 404
    assert response.json()["error"] == {
        "code": "NOT_FOUND",
        "message": f"Conversation not found: {conversation.id}",
        "retryable": False,
        "details": {"request_id": "req-upload-owner"},
    }
    assert storage.uploads == []
    assert kb_provider.requests == []


@pytest.mark.asyncio
async def test_upload_conversation_file_rejects_unsupported_or_mismatched_type(
    route_client,
    db_session,
) -> None:
    organization = await OrganizationRepository(db_session).create(
        name="Playbook Athletics",
        slug="playbook",
    )
    athlete = await UserRepository(db_session).create(
        organization_id=organization.id,
        email="athlete@example.com",
        name="Jordan Athlete",
        auth_provider="google",
        provider_subject="athlete-upload-type-subject",
    )
    conversation = await ConversationRepository(db_session).create(
        organization_id=organization.id,
        athlete_id=athlete.id,
    )
    route_client.authenticate_as(athlete)
    storage, kb_provider = _override_file_upload_dependencies(route_client)

    unsupported = await route_client.client.post(
        f"/api/v1/conversations/{conversation.id}/files",
        files={"file": ("notes.txt", b"notes", "text/plain")},
    )
    mismatched = await route_client.client.post(
        f"/api/v1/conversations/{conversation.id}/files",
        files={"file": ("contract.pdf", b"%PDF-1.7", "application/octet-stream")},
    )

    assert unsupported.status_code == 415
    assert unsupported.json()["error"]["code"] == "UNSUPPORTED_FILE_TYPE"
    assert mismatched.status_code == 415
    assert mismatched.json()["error"]["code"] == "UNSUPPORTED_FILE_TYPE"
    assert storage.uploads == []
    assert kb_provider.requests == []


@pytest.mark.asyncio
async def test_upload_conversation_file_rejects_empty_or_oversize_file(
    route_client,
    db_session,
) -> None:
    organization = await OrganizationRepository(db_session).create(
        name="Playbook Athletics",
        slug="playbook",
    )
    athlete = await UserRepository(db_session).create(
        organization_id=organization.id,
        email="athlete@example.com",
        name="Jordan Athlete",
        auth_provider="google",
        provider_subject="athlete-upload-size-subject",
    )
    conversation = await ConversationRepository(db_session).create(
        organization_id=organization.id,
        athlete_id=athlete.id,
    )
    route_client.authenticate_as(athlete)
    storage, kb_provider = _override_file_upload_dependencies(route_client)

    empty = await route_client.client.post(
        f"/api/v1/conversations/{conversation.id}/files",
        files={"file": ("empty.pdf", b"", "application/pdf")},
    )
    oversize = await route_client.client.post(
        f"/api/v1/conversations/{conversation.id}/files",
        files={
            "file": (
                "too-large.pdf",
                b"0" * (201 * 1024 * 1024),
                "application/pdf",
            )
        },
    )

    assert empty.status_code == 400
    assert empty.json()["error"]["code"] == "VALIDATION_ERROR"
    assert oversize.status_code == 413
    assert oversize.json()["error"]["code"] == "FILE_TOO_LARGE"
    assert storage.uploads == []
    assert kb_provider.requests == []


@pytest.mark.asyncio
async def test_create_conversation_validates_initial_message(
    route_client,
    db_session,
) -> None:
    organization = await OrganizationRepository(db_session).create(
        name="Playbook Athletics",
        slug="playbook",
    )
    athlete = await UserRepository(db_session).create(
        organization_id=organization.id,
        email="athlete@example.com",
        name="Jordan Athlete",
        auth_provider="google",
        provider_subject="athlete-subject",
        sport_team="Basketball",
    )
    route_client.authenticate_as(athlete)

    response = await route_client.client.post(
        "/api/v1/conversations",
        json={"initial_message": "   "},
        headers={"X-Request-ID": "req-initial-message"},
    )

    assert response.status_code == 422
    error = response.json()["error"]
    assert error["code"] == "VALIDATION_ERROR"
    assert error["details"]["request_id"] == "req-initial-message"


@pytest.mark.asyncio
async def test_submit_message_persists_placeholder_and_dispatches_task(
    route_client,
    db_session,
    monkeypatch,
) -> None:
    organization = await OrganizationRepository(db_session).create(
        name="Playbook Athletics",
        slug="playbook",
    )
    athlete = await UserRepository(db_session).create(
        organization_id=organization.id,
        email="athlete@example.com",
        name="Jordan Athlete",
        auth_provider="google",
        provider_subject="athlete-submit-subject",
        sport_team="Basketball",
    )
    conversation = await ConversationRepository(db_session).create(
        organization_id=organization.id,
        athlete_id=athlete.id,
        title="NIL question",
    )
    file = await ConversationFileRepository(db_session).create(
        conversation_id=conversation.id,
        uploaded_by=athlete.id,
        filename="nil-contract.pdf",
        content_type="application/pdf",
        size_bytes=123456,
        storage_key="conversations/org/conversation/file/nil-contract.pdf",
    )
    route_client.authenticate_as(athlete)
    dispatched: dict[str, object] = {}

    def fake_apply_async(*, kwargs: dict[str, object], task_id: str) -> SimpleNamespace:
        dispatched["kwargs"] = kwargs
        dispatched["task_id"] = task_id
        return SimpleNamespace(id=task_id)

    monkeypatch.setattr(
        worker_tasks.run_athlete_chat_task,
        "apply_async",
        fake_apply_async,
    )

    response = await route_client.client.post(
        f"/api/v1/conversations/{conversation.id}/messages",
        json={
            "content": " Can I still accept this NIL deal? ",
            "file_ids": [str(file.id)],
        },
    )

    assert response.status_code == 202
    body = response.json()
    assert body["status"] == "streaming"
    assert body["stream_url"] == (
        f"/api/v1/conversations/{conversation.id}/messages/"
        f"{body['assistant_message_id']}/stream?task_id={body['task_id']}"
    )
    assert dispatched["task_id"] == body["task_id"]
    assert dispatched["kwargs"] == {
        "conversation_id": str(conversation.id),
        "athlete_user_id": str(athlete.id),
        "user_message_id": body["user_message_id"],
        "assistant_message_id": body["assistant_message_id"],
        "organization_id": str(organization.id),
        "attached_file_ids": [str(file.id)],
    }

    messages = await ConversationMessageRepository(db_session).list_by_conversation(
        conversation.id
    )
    assert [message.role for message in messages] == ["user", "assistant"]
    assert messages[0].id == UUID(body["user_message_id"])
    assert messages[0].content == "Can I still accept this NIL deal?"
    assert messages[0].status == "complete"
    assert messages[0].message_metadata == {"attached_file_ids": [str(file.id)]}
    assert messages[1].id == UUID(body["assistant_message_id"])
    assert messages[1].content == ""
    assert messages[1].status == "streaming"
    assert messages[1].message_metadata["task_id"] == body["task_id"]
    assert messages[1].message_metadata["user_message_id"] == body["user_message_id"]
    assert conversation.last_message_at == messages[0].created_at


@pytest.mark.asyncio
async def test_submit_message_validates_content(route_client, db_session) -> None:
    organization = await OrganizationRepository(db_session).create(
        name="Playbook Athletics",
        slug="playbook",
    )
    athlete = await UserRepository(db_session).create(
        organization_id=organization.id,
        email="athlete@example.com",
        name="Jordan Athlete",
        auth_provider="google",
        provider_subject="athlete-blank-submit",
    )
    conversation = await ConversationRepository(db_session).create(
        organization_id=organization.id,
        athlete_id=athlete.id,
    )
    route_client.authenticate_as(athlete)

    response = await route_client.client.post(
        f"/api/v1/conversations/{conversation.id}/messages",
        json={"content": "   "},
        headers={"X-Request-ID": "req-submit-blank"},
    )

    assert response.status_code == 422
    error = response.json()["error"]
    assert error["code"] == "VALIDATION_ERROR"
    assert error["details"]["request_id"] == "req-submit-blank"


@pytest.mark.asyncio
async def test_submit_message_is_scoped_to_current_athlete(
    route_client,
    db_session,
    monkeypatch,
) -> None:
    organization = await OrganizationRepository(db_session).create(
        name="Playbook Athletics",
        slug="playbook",
    )
    user_repo = UserRepository(db_session)
    owner = await user_repo.create(
        organization_id=organization.id,
        email="owner@example.com",
        name="Owner Athlete",
        auth_provider="google",
        provider_subject="owner-submit-subject",
    )
    other = await user_repo.create(
        organization_id=organization.id,
        email="other@example.com",
        name="Other Athlete",
        auth_provider="google",
        provider_subject="other-submit-subject",
    )
    conversation = await ConversationRepository(db_session).create(
        organization_id=organization.id,
        athlete_id=owner.id,
        title="Private NIL question",
    )
    route_client.authenticate_as(other)

    def fail_apply_async(**_: object) -> None:
        pytest.fail("submit must not dispatch for another athlete's conversation")

    monkeypatch.setattr(
        worker_tasks.run_athlete_chat_task,
        "apply_async",
        fail_apply_async,
    )

    response = await route_client.client.post(
        f"/api/v1/conversations/{conversation.id}/messages",
        json={"content": "Can I follow up?"},
        headers={"X-Request-ID": "req-submit-owner"},
    )

    assert response.status_code == 404
    assert response.json()["error"] == {
        "code": "NOT_FOUND",
        "message": f"Conversation not found: {conversation.id}",
        "retryable": False,
        "details": {"request_id": "req-submit-owner"},
    }


@pytest.mark.asyncio
async def test_submit_message_rejects_files_outside_conversation(
    route_client,
    db_session,
    monkeypatch,
) -> None:
    organization = await OrganizationRepository(db_session).create(
        name="Playbook Athletics",
        slug="playbook",
    )
    athlete = await UserRepository(db_session).create(
        organization_id=organization.id,
        email="athlete@example.com",
        name="Jordan Athlete",
        auth_provider="google",
        provider_subject="athlete-file-submit-subject",
    )
    conversation = await ConversationRepository(db_session).create(
        organization_id=organization.id,
        athlete_id=athlete.id,
    )
    other_conversation = await ConversationRepository(db_session).create(
        organization_id=organization.id,
        athlete_id=athlete.id,
    )
    other_file = await ConversationFileRepository(db_session).create(
        conversation_id=other_conversation.id,
        uploaded_by=athlete.id,
        filename="other.pdf",
        content_type="application/pdf",
        size_bytes=1,
        storage_key="conversations/org/other/file/other.pdf",
    )
    route_client.authenticate_as(athlete)

    def fail_apply_async(**_: object) -> None:
        pytest.fail("submit must not dispatch when file_ids are invalid")

    monkeypatch.setattr(
        worker_tasks.run_athlete_chat_task,
        "apply_async",
        fail_apply_async,
    )

    response = await route_client.client.post(
        f"/api/v1/conversations/{conversation.id}/messages",
        json={"content": "Use this file", "file_ids": [str(other_file.id)]},
        headers={"X-Request-ID": "req-submit-file"},
    )

    assert response.status_code == 400
    assert response.json()["error"] == {
        "code": "VALIDATION_ERROR",
        "message": "One or more file_ids are not available for this conversation",
        "retryable": False,
        "details": {"request_id": "req-submit-file"},
    }


@pytest.mark.asyncio
async def test_stream_message_emits_seeded_sse_events(
    route_client,
    db_session,
) -> None:
    organization = await OrganizationRepository(db_session).create(
        name="Playbook Athletics",
        slug="playbook",
    )
    athlete = await UserRepository(db_session).create(
        organization_id=organization.id,
        email="athlete@example.com",
        name="Jordan Athlete",
        auth_provider="google",
        provider_subject="athlete-stream-subject",
    )
    conversation = await ConversationRepository(db_session).create(
        organization_id=organization.id,
        athlete_id=athlete.id,
    )
    assistant_message = await ConversationMessageRepository(db_session).create(
        conversation_id=conversation.id,
        role="assistant",
        content="",
        status="streaming",
        metadata={"task_id": "task-stream-123"},
    )
    provider = InMemoryAgentStreamProvider()
    stream_service = AgentStreamService(provider)
    await stream_service.publish_progress("task-stream-123", status="retrieving")
    await stream_service.publish_chunk("task-stream-123", content="Hello")
    await stream_service.publish_complete(
        "task-stream-123",
        data={"assistant_message_id": str(assistant_message.id)},
    )
    route_client.app.dependency_overrides[get_agent_stream_service] = (
        lambda: AgentStreamService(provider)
    )
    route_client.authenticate_as(athlete)

    response = await route_client.client.get(
        f"/api/v1/conversations/{conversation.id}/messages/"
        f"{assistant_message.id}/stream?task_id=task-stream-123"
    )

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/event-stream")
    assert response.headers["cache-control"] == "no-cache"
    assert response.headers["x-accel-buffering"] == "no"
    assert "id: 1-0\nevent: progress\n" in response.text
    assert "id: 2-0\nevent: chunk\n" in response.text
    assert '"content":"Hello"' in response.text
    assert "id: 3-0\nevent: complete\n" in response.text


@pytest.mark.asyncio
async def test_stream_message_resumes_from_after_id_and_last_event_id(
    route_client,
    db_session,
) -> None:
    organization = await OrganizationRepository(db_session).create(
        name="Playbook Athletics",
        slug="playbook",
    )
    athlete = await UserRepository(db_session).create(
        organization_id=organization.id,
        email="athlete@example.com",
        name="Jordan Athlete",
        auth_provider="google",
        provider_subject="athlete-stream-resume-subject",
    )
    conversation = await ConversationRepository(db_session).create(
        organization_id=organization.id,
        athlete_id=athlete.id,
    )
    assistant_message = await ConversationMessageRepository(db_session).create(
        conversation_id=conversation.id,
        role="assistant",
        content="",
        status="streaming",
        metadata={"task_id": "task-stream-resume"},
    )
    provider = InMemoryAgentStreamProvider()
    stream_service = AgentStreamService(provider)
    await stream_service.publish_chunk("task-stream-resume", content="first")
    await stream_service.publish_chunk("task-stream-resume", content="second")
    await stream_service.publish_complete("task-stream-resume")
    route_client.app.dependency_overrides[get_agent_stream_service] = (
        lambda: AgentStreamService(provider)
    )
    route_client.authenticate_as(athlete)

    response = await route_client.client.get(
        f"/api/v1/conversations/{conversation.id}/messages/"
        f"{assistant_message.id}/stream?task_id=task-stream-resume&after_id=0-0",
        headers={"Last-Event-ID": "1-0"},
    )

    assert response.status_code == 200
    assert "id: 1-0" not in response.text
    assert "id: 2-0\nevent: chunk\n" in response.text
    assert '"content":"second"' in response.text
    assert "id: 3-0\nevent: complete\n" in response.text


@pytest.mark.asyncio
async def test_stream_message_validates_athlete_message_and_task_binding(
    route_client,
    db_session,
) -> None:
    organization = await OrganizationRepository(db_session).create(
        name="Playbook Athletics",
        slug="playbook",
    )
    owner = await UserRepository(db_session).create(
        organization_id=organization.id,
        email="owner@example.com",
        name="Owner Athlete",
        auth_provider="google",
        provider_subject="athlete-stream-owner",
    )
    other = await UserRepository(db_session).create(
        organization_id=organization.id,
        email="other@example.com",
        name="Other Athlete",
        auth_provider="google",
        provider_subject="athlete-stream-other",
    )
    conversation = await ConversationRepository(db_session).create(
        organization_id=organization.id,
        athlete_id=owner.id,
    )
    assistant_message = await ConversationMessageRepository(db_session).create(
        conversation_id=conversation.id,
        role="assistant",
        content="",
        status="streaming",
        metadata={"task_id": "task-owner"},
    )
    route_client.app.dependency_overrides[get_agent_stream_service] = (
        lambda: AgentStreamService(InMemoryAgentStreamProvider())
    )

    route_client.authenticate_as(owner)
    wrong_task_response = await route_client.client.get(
        f"/api/v1/conversations/{conversation.id}/messages/"
        f"{assistant_message.id}/stream?task_id=wrong-task",
        headers={"X-Request-ID": "req-wrong-task"},
    )
    route_client.authenticate_as(other)
    wrong_athlete_response = await route_client.client.get(
        f"/api/v1/conversations/{conversation.id}/messages/"
        f"{assistant_message.id}/stream?task_id=task-owner",
        headers={"X-Request-ID": "req-wrong-athlete"},
    )

    assert wrong_task_response.status_code == 404
    assert wrong_task_response.json()["error"]["code"] == "NOT_FOUND"
    assert wrong_task_response.json()["error"]["details"]["request_id"] == (
        "req-wrong-task"
    )
    assert wrong_athlete_response.status_code == 404
    assert wrong_athlete_response.json()["error"]["code"] == "NOT_FOUND"
    assert wrong_athlete_response.json()["error"]["details"]["request_id"] == (
        "req-wrong-athlete"
    )


@pytest.mark.asyncio
async def test_conversation_create_openapi_uses_initial_message(route_client) -> None:
    response = await route_client.client.get("/openapi.json")

    assert response.status_code == 200
    schema = response.json()["components"]["schemas"]["ConversationCreateRequest"]
    submit_schema = response.json()["components"]["schemas"]["MessageSubmitRequest"]
    submit_response_schema = response.json()["components"]["schemas"][
        "MessageSubmitResponse"
    ]
    detail_schema = response.json()["components"]["schemas"][
        "ConversationDetailResponse"
    ]
    assert "initial_message" in schema["properties"]
    assert "title" not in schema["properties"]
    assert "initial_message" in schema["required"]
    assert "content" in submit_schema["properties"]
    assert "file_ids" in submit_schema["properties"]
    assert "content" in submit_schema["required"]
    assert "task_id" in submit_response_schema["properties"]
    assert "stream_url" in submit_response_schema["properties"]
    assert "files" in detail_schema["properties"]
    assert (
        "/api/v1/conversations/{conversation_id}/messages/{message_id}/stream"
        in response.json()["paths"]
    )
    assert "/api/v1/conversations/{conversation_id}/files" in response.json()["paths"]


@pytest.mark.asyncio
async def test_conversation_detail_is_scoped_to_current_athlete(
    route_client,
    db_session,
) -> None:
    organization = await OrganizationRepository(db_session).create(
        name="Playbook Athletics",
        slug="playbook",
    )
    user_repo = UserRepository(db_session)
    owner = await user_repo.create(
        organization_id=organization.id,
        email="owner@example.com",
        name="Owner Athlete",
        auth_provider="google",
        provider_subject="owner-subject",
    )
    other = await user_repo.create(
        organization_id=organization.id,
        email="other@example.com",
        name="Other Athlete",
        auth_provider="google",
        provider_subject="other-subject",
    )
    conversation = await ConversationRepository(db_session).create(
        organization_id=organization.id,
        athlete_id=owner.id,
        title="Private NIL question",
    )
    route_client.authenticate_as(other)

    response = await route_client.client.get(
        f"/api/v1/conversations/{conversation.id}",
        headers={"X-Request-ID": "req-convo-owner"},
    )

    assert response.status_code == 404
    assert response.json()["error"] == {
        "code": "NOT_FOUND",
        "message": f"Conversation not found: {conversation.id}",
        "retryable": False,
        "details": {"request_id": "req-convo-owner"},
    }


@pytest.mark.asyncio
async def test_conversation_routes_require_athlete_role(route_client, db_session) -> None:
    organization = await OrganizationRepository(db_session).create(
        name="Playbook Athletics",
        slug="playbook",
    )
    admin = await UserRepository(db_session).create(
        organization_id=organization.id,
        email="admin@example.com",
        name="Admin User",
        auth_provider="google",
        provider_subject="admin-subject",
        role="admin",
    )
    route_client.authenticate_as(admin)

    response = await route_client.client.get(
        "/api/v1/conversations",
        headers={"X-Request-ID": "req-convo-role"},
    )

    assert response.status_code == 403
    assert response.json()["error"] == {
        "code": "FORBIDDEN",
        "message": "Athlete role required",
        "retryable": False,
        "details": {"request_id": "req-convo-role"},
    }
