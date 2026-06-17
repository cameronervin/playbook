"""Route-level tests for admin KB document endpoints."""

from __future__ import annotations

from typing import BinaryIO
from uuid import UUID, uuid4
from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import select

from app.infrastructure.knowledgebase import get_kb_provider_dependency
from app.infrastructure.storage import get_storage_provider_dependency
from app.infrastructure.storage.provider import PresignedPostUpload, StoredObjectMetadata
from app.models.audit import AuditLog
from app.models.knowledge_base import KBDocument, KBDocumentEvent
from app.repositories.identity import OrganizationRepository, UserRepository
from app.schemas.knowledgebase import (
    KBDocumentIngestRequest,
    KBDocumentIngestResponse,
    KBDocumentStatusResponse,
    KnowledgebaseResult,
)


class FakeStorageProvider:
    """Storage fake that records file operations."""

    def __init__(self) -> None:
        self.uploads: list[tuple[str, str, int]] = []
        self.deletes: list[str] = []

    async def upload_file(self, key: str, file: BinaryIO, content_type: str) -> str:
        data = file.read()
        file.seek(0)
        self.uploads.append((key, content_type, len(data)))
        return key

    async def download_file(self, key: str) -> bytes:
        return b"document"

    async def delete_file(self, key: str) -> None:
        self.deletes.append(key)

    async def get_presigned_url(
        self,
        key: str,
        expires_in: int = 3600,
        download_filename: str | None = None,
    ) -> str:
        return f"https://storage.example/{key}?filename={download_filename}"

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
            expires_at=datetime.now(UTC) + timedelta(seconds=expires_in or 900),
        )

    async def get_object_metadata(self, key: str) -> StoredObjectMetadata | None:
        return StoredObjectMetadata(
            key=key,
            content_length=123,
            content_type="application/pdf",
        )

    async def file_exists(self, key: str) -> bool:
        return True


class FakeKnowledgebaseProvider:
    """Knowledgebase fake that records ingestion/deletion calls."""

    def __init__(self) -> None:
        self.ingest_requests: list[KBDocumentIngestRequest] = []
        self.deleted_document_ids: list[str] = []
        self.retried_document_ids: list[str] = []

    @property
    def provider_name(self) -> str:
        return "fake"

    async def search(
        self,
        query: str,
        organization_id: UUID | str,
        max_docs: int = 10,
        score_threshold: float = 0.7,
        metadata_filter: dict | None = None,
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

    async def ingest_document(
        self,
        request: KBDocumentIngestRequest,
    ) -> KBDocumentIngestResponse:
        self.ingest_requests.append(request)
        return KBDocumentIngestResponse(
            kb_service_document_id=uuid4(),
            playbook_document_id=request.playbook_document_id,
            task_id=f"task-{len(self.ingest_requests)}",
        )

    async def get_document_status(self, document_id: str) -> KBDocumentStatusResponse:
        return KBDocumentStatusResponse(task_id=document_id, status="pending")

    async def retry_document(
        self,
        kb_service_document_id: str,
    ) -> KBDocumentIngestResponse:
        self.retried_document_ids.append(kb_service_document_id)
        return KBDocumentIngestResponse(
            kb_service_document_id=UUID(kb_service_document_id),
            playbook_document_id=self.ingest_requests[0].playbook_document_id,
            task_id=f"retry-task-{len(self.retried_document_ids)}",
        )

    async def delete_document(self, kb_service_document_id: str) -> None:
        self.deleted_document_ids.append(kb_service_document_id)


async def _admin_user(db_session):
    organization = await OrganizationRepository(db_session).create(
        name="Playbook Athletics",
        slug="playbook",
    )
    return await UserRepository(db_session).create(
        organization_id=organization.id,
        email="admin@example.com",
        name="Admin User",
        auth_provider="google",
        provider_subject="admin-subject",
        role="admin",
    )


def _override_external_providers(route_client):
    storage = FakeStorageProvider()
    kb_provider = FakeKnowledgebaseProvider()
    route_client.app.dependency_overrides[get_storage_provider_dependency] = (
        lambda: storage
    )
    route_client.app.dependency_overrides[get_kb_provider_dependency] = (
        lambda: kb_provider
    )
    return storage, kb_provider


@pytest.mark.asyncio
async def test_admin_kb_document_lifecycle_routes(route_client, db_session) -> None:
    admin = await _admin_user(db_session)
    route_client.authenticate_as(admin)
    storage, kb_provider = _override_external_providers(route_client)

    upload = await route_client.client.post(
        "/api/v1/admin/kb/documents",
        data={
            "title": "NIL Handbook",
            "metadata_tags": '{"topic":"nil","source_type":"policy"}',
            "source_date": "2026-01-15",
        },
        files={"file": ("nil-handbook.pdf", b"NIL policy", "application/pdf")},
    )

    assert upload.status_code == 201
    uploaded = upload.json()
    document_id = UUID(uploaded["id"])
    assert uploaded["metadata_tags"] == {"topic": "nil", "source_type": "policy"}
    assert "is_official" not in uploaded
    assert "priority" not in uploaded
    assert storage.uploads[0][1] == "application/pdf"
    assert kb_provider.ingest_requests[0].metadata_tags == {
        "topic": "nil",
        "source_type": "policy",
    }
    assert kb_provider.ingest_requests[0].organization_id == admin.organization_id
    assert kb_provider.ingest_requests[0].is_official is True
    assert kb_provider.ingest_requests[0].priority == 0

    list_response = await route_client.client.get("/api/v1/admin/kb/documents")
    get_response = await route_client.client.get(
        f"/api/v1/admin/kb/documents/{document_id}"
    )
    update_response = await route_client.client.patch(
        f"/api/v1/admin/kb/documents/{document_id}/metadata",
        json={"metadata_tags": {"topic": "compliance"}},
    )
    retry_response = await route_client.client.post(
        f"/api/v1/admin/kb/documents/{document_id}/retry"
    )

    assert list_response.status_code == 200
    assert [row["id"] for row in list_response.json()] == [str(document_id)]
    assert get_response.status_code == 200
    assert get_response.json()["id"] == str(document_id)
    assert "is_official" not in get_response.json()
    assert "priority" not in get_response.json()
    assert update_response.status_code == 200
    assert update_response.json()["metadata_tags"] == {"topic": "compliance"}
    assert "is_official" not in update_response.json()
    assert "priority" not in update_response.json()
    assert retry_response.status_code == 200
    assert retry_response.json()["processing_status"] == "uploaded"
    assert len(kb_provider.ingest_requests) == 1
    assert kb_provider.retried_document_ids == [
        str(uploaded["kb_service_document_id"])
    ]

    events = list(
        (
            await db_session.scalars(
                select(KBDocumentEvent).where(KBDocumentEvent.document_id == document_id)
            )
        ).all()
    )
    assert {event.event_type for event in events} == {
        "document.uploaded",
        "ingestion.requested",
        "document.metadata_updated",
        "ingestion.retry_requested",
    }

    persisted = await db_session.get(KBDocument, document_id)
    assert persisted is not None
    assert persisted.is_official is True
    assert persisted.priority == 0
    linked_id = persisted.kb_service_document_id

    delete_response = await route_client.client.delete(
        f"/api/v1/admin/kb/documents/{document_id}"
    )

    assert delete_response.status_code == 204
    assert storage.deletes == [persisted.storage_key]
    assert kb_provider.deleted_document_ids == [str(linked_id)]
    assert await db_session.get(KBDocument, document_id) is None

    audit_actions = set(
        (
            await db_session.scalars(
                select(AuditLog.action).where(AuditLog.target_id == document_id)
            )
        ).all()
    )
    assert audit_actions == {
        "kb.document_uploaded",
        "kb.document_metadata_updated",
        "kb.document_retry_requested",
        "kb.document_deleted",
    }


@pytest.mark.asyncio
async def test_kb_upload_rejects_invalid_metadata_json(route_client, db_session) -> None:
    admin = await _admin_user(db_session)
    route_client.authenticate_as(admin)
    _override_external_providers(route_client)

    response = await route_client.client.post(
        "/api/v1/admin/kb/documents",
        data={"metadata_tags": "not-json"},
        files={"file": ("nil-handbook.pdf", b"NIL policy", "application/pdf")},
        headers={"X-Request-ID": "req-kb-json"},
    )

    assert response.status_code == 400
    assert response.json()["error"] == {
        "code": "VALIDATION_ERROR",
        "message": "metadata_tags must be a JSON object",
        "retryable": False,
        "details": {"request_id": "req-kb-json"},
    }


@pytest.mark.asyncio
async def test_kb_upload_rejects_metadata_json_array(route_client, db_session) -> None:
    admin = await _admin_user(db_session)
    route_client.authenticate_as(admin)
    _override_external_providers(route_client)

    response = await route_client.client.post(
        "/api/v1/admin/kb/documents",
        data={"metadata_tags": '["nil"]'},
        files={"file": ("nil-handbook.pdf", b"NIL policy", "application/pdf")},
        headers={"X-Request-ID": "req-kb-array"},
    )

    assert response.status_code == 400
    assert response.json()["error"] == {
        "code": "VALIDATION_ERROR",
        "message": "metadata_tags must be a JSON object",
        "retryable": False,
        "details": {"request_id": "req-kb-array"},
    }


@pytest.mark.asyncio
async def test_kb_upload_openapi_documents_metadata_tags_json_string(
    route_client,
) -> None:
    response = await route_client.client.get("/openapi.json")

    assert response.status_code == 200
    upload_properties = response.json()["components"]["schemas"][
        "Body_upload_document_api_v1_admin_kb_documents_post"
    ]["properties"]
    metadata_tags = upload_properties["metadata_tags"]
    assert "JSON object encoded as a string" in metadata_tags["description"]
    assert metadata_tags["examples"] == ['{"topic":"nil","source_type":"policy"}']
    assert "is_official" not in upload_properties
    assert "priority" not in upload_properties

    document_properties = response.json()["components"]["schemas"][
        "KBDocumentResponse"
    ]["properties"]
    assert "is_official" not in document_properties
    assert "priority" not in document_properties


@pytest.mark.asyncio
async def test_kb_upload_rejects_unsupported_content_type(
    route_client,
    db_session,
) -> None:
    admin = await _admin_user(db_session)
    route_client.authenticate_as(admin)
    _override_external_providers(route_client)

    response = await route_client.client.post(
        "/api/v1/admin/kb/documents",
        files={"file": ("notes.txt", b"notes", "text/plain")},
        headers={"X-Request-ID": "req-kb-type"},
    )

    assert response.status_code == 415
    assert response.json()["error"]["code"] == "UNSUPPORTED_FILE_TYPE"
    assert response.json()["error"]["details"]["request_id"] == "req-kb-type"


@pytest.mark.asyncio
async def test_kb_document_routes_require_admin(route_client, db_session) -> None:
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
        role="athlete",
    )
    route_client.authenticate_as(athlete)

    response = await route_client.client.get(
        "/api/v1/admin/kb/documents",
        headers={"X-Request-ID": "req-kb-admin"},
    )

    assert response.status_code == 403
    assert response.json()["error"] == {
        "code": "FORBIDDEN",
        "message": "Admin role required",
        "retryable": False,
        "details": {"request_id": "req-kb-admin"},
    }
