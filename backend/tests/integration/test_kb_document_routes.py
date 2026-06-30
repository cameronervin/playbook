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
from app.models.uploads import KBIngestOutbox, UploadRequest
from app.repositories.knowledge_base import KBDocumentRepository
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
        self.presigned_posts: list[tuple[str, str, int]] = []
        self.deletes: list[str] = []
        self.objects: dict[str, StoredObjectMetadata | None] = {}

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
        self.presigned_posts.append((key, content_type, max_size_bytes))
        return PresignedPostUpload(
            url="https://storage.example/upload",
            fields={"key": key, "Content-Type": content_type},
            expires_at=datetime.now(UTC) + timedelta(seconds=expires_in or 900),
        )

    async def get_object_metadata(self, key: str) -> StoredObjectMetadata | None:
        return self.objects.get(key)

    async def verify_object(
        self,
        *,
        key: str,
        expected_size_bytes: int,
        expected_content_type: str,
    ):
        from app.infrastructure.storage.provider import ObjectVerificationResult

        metadata = await self.get_object_metadata(key)
        if metadata is None:
            return ObjectVerificationResult(status="missing")
        if metadata.content_length != expected_size_bytes:
            return ObjectVerificationResult(status="size_mismatch", metadata=metadata)
        if metadata.content_type != expected_content_type:
            return ObjectVerificationResult(
                status="content_type_mismatch",
                metadata=metadata,
            )
        return ObjectVerificationResult(status="valid", metadata=metadata)

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
            playbook_document_id=(
                self.ingest_requests[0].playbook_document_id
                if self.ingest_requests
                else None
            ),
            task_id=f"retry-task-{len(self.retried_document_ids)}",
        )

    async def delete_document(self, kb_service_document_id: str) -> None:
        self.deleted_document_ids.append(kb_service_document_id)


async def _admin_user(db_session, *, role: str = "admin"):
    organization = await OrganizationRepository(db_session).create(
        name="Playbook Athletics",
        slug="playbook",
    )
    return await UserRepository(db_session).create(
        organization_id=organization.id,
        email="admin@example.com",
        name="Admin User",
        auth_provider="google",
        provider_subject=f"{role}-subject",
        role=role,
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
async def test_kb_catalog_routes_seed_defaults_and_require_super_admin_for_writes(
    route_client,
    db_session,
) -> None:
    admin = await _admin_user(db_session)
    route_client.authenticate_as(admin)

    collections = await route_client.client.get("/api/v1/admin/kb/collections")
    tags = await route_client.client.get("/api/v1/admin/kb/metadata-tags")
    denied_collection = await route_client.client.post(
        "/api/v1/admin/kb/collections",
        json={
            "title": "Sports Medicine",
            "description": "Athletic training process documents.",
            "icon": "database",
        },
        headers={"X-Request-ID": "req-kb-collection-denied"},
    )
    denied_tag = await route_client.client.post(
        "/api/v1/admin/kb/metadata-tags",
        json={"label": "Medical"},
        headers={"X-Request-ID": "req-kb-tag-denied"},
    )

    assert collections.status_code == 200
    assert [item["slug"] for item in collections.json()] == [
        "compliance",
        "travel",
        "academics",
        "donor",
    ]
    assert collections.json()[0]["description"].startswith("NIL, eligibility")
    assert tags.status_code == 200
    assert {"nil", "compliance", "recruiting"}.issubset(
        {item["slug"] for item in tags.json()}
    )
    assert denied_collection.status_code == 403
    assert denied_tag.status_code == 403


@pytest.mark.asyncio
async def test_super_admin_can_create_collections_and_manage_metadata_tags(
    route_client,
    db_session,
) -> None:
    super_admin = await _admin_user(db_session, role="super_admin")
    route_client.authenticate_as(super_admin)

    collection_response = await route_client.client.post(
        "/api/v1/admin/kb/collections",
        json={
            "title": "Sports Medicine",
            "description": "Athletic training process documents.",
            "icon": "database",
        },
    )
    tag_response = await route_client.client.post(
        "/api/v1/admin/kb/metadata-tags",
        json={"label": "Medical Referral"},
    )

    assert collection_response.status_code == 201
    assert collection_response.json()["slug"] == "sports-medicine"
    assert collection_response.json()["title"] == "Sports Medicine"
    assert collection_response.json()["description"] == "Athletic training process documents."
    assert tag_response.status_code == 201
    assert tag_response.json()["slug"] == "medical-referral"
    tag_id = tag_response.json()["id"]

    renamed = await route_client.client.patch(
        f"/api/v1/admin/kb/metadata-tags/{tag_id}",
        json={"label": "Medical referrals"},
    )
    archived = await route_client.client.delete(
        f"/api/v1/admin/kb/metadata-tags/{tag_id}"
    )
    active_tags = await route_client.client.get("/api/v1/admin/kb/metadata-tags")
    all_tags = await route_client.client.get(
        "/api/v1/admin/kb/metadata-tags?include_archived=true"
    )

    assert renamed.status_code == 200
    assert renamed.json()["slug"] == "medical-referral"
    assert renamed.json()["label"] == "Medical referrals"
    assert archived.status_code == 204
    assert "medical-referral" not in {item["slug"] for item in active_tags.json()}
    archived_row = next(item for item in all_tags.json() if item["slug"] == "medical-referral")
    assert archived_row["is_active"] is False


@pytest.mark.asyncio
async def test_admin_kb_document_lifecycle_routes(route_client, db_session) -> None:
    admin = await _admin_user(db_session)
    route_client.authenticate_as(admin)
    storage, kb_provider = _override_external_providers(route_client)
    collections_response = await route_client.client.get("/api/v1/admin/kb/collections")
    tags_response = await route_client.client.get("/api/v1/admin/kb/metadata-tags")
    collection = next(
        item for item in collections_response.json() if item["slug"] == "compliance"
    )
    nil_tag = next(item for item in tags_response.json() if item["slug"] == "nil")

    upload = await route_client.client.post(
        "/api/v1/admin/kb/documents",
        json={
            "filename": "nil-handbook.pdf",
            "content_type": "application/pdf",
            "size_bytes": 10,
            "collection_id": collection["id"],
            "tag_slugs": [nil_tag["slug"]],
            "title": "NIL Handbook",
            "source_date": "2026-01-15",
        },
    )

    assert upload.status_code == 201
    uploaded = upload.json()
    document = uploaded["document"]
    document_id = UUID(document["id"])
    upload_request_id = UUID(uploaded["upload"]["upload_request_id"])
    storage_key = uploaded["upload"]["fields"]["key"]
    assert document["processing_status"] == "upload_pending"
    assert document["collection_id"] == collection["id"]
    assert document["tag_slugs"] == ["nil"]
    assert document["metadata_tags"] == {
        "collection": "compliance",
        "collection_title": "Compliance & NIL",
        "tag_slugs": ["nil"],
        "tags": ["NIL"],
        "topics": ["Compliance & NIL", "NIL"],
    }
    assert "is_official" not in document
    assert "priority" not in document
    assert storage.uploads == []
    assert storage.presigned_posts == [(storage_key, "application/pdf", 10)]
    assert (
        storage_key
        == f"kb/originals/{admin.organization_id}/{document_id}/nil-handbook.pdf"
    )
    assert kb_provider.ingest_requests == []

    upload_request = await db_session.get(UploadRequest, upload_request_id)
    assert upload_request is not None
    assert upload_request.kb_document_id == document_id
    assert upload_request.status == "pending"

    storage.objects[storage_key] = StoredObjectMetadata(
        key=storage_key,
        content_length=10,
        content_type="application/pdf",
    )
    complete_response = await route_client.client.post(
        f"/api/v1/admin/kb/documents/{document_id}/upload-complete",
        json={"upload_request_id": str(upload_request_id)},
    )

    assert complete_response.status_code == 200
    completed = complete_response.json()
    assert completed["processing_status"] == "uploaded"
    assert completed["tag_slugs"] == ["nil"]
    assert "storage_key" not in completed
    assert kb_provider.ingest_requests == []
    outbox_rows = list((await db_session.scalars(select(KBIngestOutbox))).all())
    assert len(outbox_rows) == 1
    assert outbox_rows[0].source_type == "admin_upload"
    assert outbox_rows[0].kb_document_id == document_id

    duplicate_complete = await route_client.client.post(
        f"/api/v1/admin/kb/documents/{document_id}/upload-complete",
        json={"upload_request_id": str(upload_request_id)},
    )

    assert duplicate_complete.status_code == 200
    assert duplicate_complete.json()["processing_status"] == "uploaded"
    assert len((await db_session.scalars(select(KBIngestOutbox))).all()) == 1

    list_response = await route_client.client.get("/api/v1/admin/kb/documents")
    get_response = await route_client.client.get(
        f"/api/v1/admin/kb/documents/{document_id}"
    )
    update_response = await route_client.client.patch(
        f"/api/v1/admin/kb/documents/{document_id}/metadata",
        json={"tag_slugs": ["compliance"]},
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
    assert update_response.json()["tag_slugs"] == ["compliance"]
    assert update_response.json()["metadata_tags"]["tags"] == ["Compliance"]
    assert "is_official" not in update_response.json()
    assert "priority" not in update_response.json()
    assert retry_response.status_code == 200
    assert retry_response.json()["processing_status"] == "uploaded"
    assert kb_provider.ingest_requests == []
    assert kb_provider.retried_document_ids == []

    events = list(
        (
            await db_session.scalars(
                select(KBDocumentEvent).where(KBDocumentEvent.document_id == document_id)
            )
        ).all()
    )
    assert {event.event_type for event in events} >= {
        "document.upload_requested",
        "document.uploaded",
        "ingestion.queued",
        "document.metadata_updated",
        "ingestion.retry_requested",
    }

    persisted = await db_session.get(KBDocument, document_id)
    assert persisted is not None
    assert persisted.is_official is True
    assert persisted.priority == 0
    assert persisted.kb_service_document_id is None

    delete_response = await route_client.client.delete(
        f"/api/v1/admin/kb/documents/{document_id}"
    )

    assert delete_response.status_code == 204
    assert storage.deletes == [persisted.storage_key]
    assert kb_provider.deleted_document_ids == []
    assert await db_session.get(KBDocument, document_id) is None

    audit_actions = set(
        (
            await db_session.scalars(
                select(AuditLog.action).where(AuditLog.target_id == document_id)
            )
        ).all()
    )
    assert audit_actions >= {
        "kb.document_upload_requested",
        "kb.document_uploaded",
        "kb.document_metadata_updated",
        "kb.document_retry_requested",
        "kb.document_deleted",
    }


@pytest.mark.asyncio
async def test_kb_upload_rejects_client_authored_metadata_tags(
    route_client,
    db_session,
) -> None:
    admin = await _admin_user(db_session)
    route_client.authenticate_as(admin)
    _override_external_providers(route_client)
    collections_response = await route_client.client.get("/api/v1/admin/kb/collections")
    collection = next(
        item for item in collections_response.json() if item["slug"] == "compliance"
    )

    response = await route_client.client.post(
        "/api/v1/admin/kb/documents",
        json={
            "filename": "nil-handbook.pdf",
            "content_type": "application/pdf",
            "size_bytes": 10,
            "metadata_tags": {"source_type": "policy"},
        },
        headers={"X-Request-ID": "req-kb-reserved"},
    )

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "VALIDATION_ERROR"


@pytest.mark.asyncio
async def test_kb_metadata_patch_rejects_client_authored_metadata_tags(
    route_client,
    db_session,
) -> None:
    admin = await _admin_user(db_session)
    route_client.authenticate_as(admin)
    _override_external_providers(route_client)
    document = await KBDocumentRepository(db_session).create(
        organization_id=admin.organization_id,
        uploaded_by=admin.id,
        title="NIL Handbook",
        filename="nil-handbook.pdf",
        content_type="application/pdf",
        size_bytes=10,
        storage_key="kb/originals/nil-handbook.pdf",
        metadata_tags={"topic": "nil"},
    )
    await db_session.commit()

    response = await route_client.client.patch(
        f"/api/v1/admin/kb/documents/{document.id}/metadata",
        json={"metadata_tags": {"source_type": "policy"}},
        headers={"X-Request-ID": "req-kb-patch-reserved"},
    )

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "VALIDATION_ERROR"
    await db_session.refresh(document)
    assert document.metadata_tags == {"topic": "nil"}


@pytest.mark.asyncio
async def test_kb_metadata_patch_preserves_omitted_source_date_and_clears_null(
    route_client,
    db_session,
) -> None:
    admin = await _admin_user(db_session)
    route_client.authenticate_as(admin)
    _override_external_providers(route_client)
    collections_response = await route_client.client.get("/api/v1/admin/kb/collections")
    collection = next(
        item for item in collections_response.json() if item["slug"] == "compliance"
    )
    document = await KBDocumentRepository(db_session).create(
        organization_id=admin.organization_id,
        uploaded_by=admin.id,
        title="NIL Handbook",
        filename="nil-handbook.pdf",
        content_type="application/pdf",
        size_bytes=10,
        storage_key="kb/originals/nil-handbook.pdf",
        collection_id=UUID(collection["id"]),
        metadata_tags={"topic": "nil"},
        source_date=datetime(2026, 1, 15, tzinfo=UTC).date(),
    )
    await db_session.commit()

    preserved = await route_client.client.patch(
        f"/api/v1/admin/kb/documents/{document.id}/metadata",
        json={"tag_slugs": ["compliance"]},
    )
    cleared = await route_client.client.patch(
        f"/api/v1/admin/kb/documents/{document.id}/metadata",
        json={"source_date": None},
    )

    assert preserved.status_code == 200
    assert preserved.json()["source_date"] == "2026-01-15"
    assert preserved.json()["tag_slugs"] == ["compliance"]
    assert cleared.status_code == 200
    assert cleared.json()["source_date"] is None
    assert cleared.json()["tag_slugs"] == ["compliance"]


@pytest.mark.asyncio
async def test_kb_retry_and_delete_call_kb_service_when_document_is_linked(
    route_client,
    db_session,
) -> None:
    admin = await _admin_user(db_session)
    route_client.authenticate_as(admin)
    storage, kb_provider = _override_external_providers(route_client)
    document = await KBDocumentRepository(db_session).create(
        organization_id=admin.organization_id,
        uploaded_by=admin.id,
        title="NIL Handbook",
        filename="nil-handbook.pdf",
        content_type="application/pdf",
        size_bytes=10,
        storage_key="kb/originals/nil-handbook.pdf",
        processing_status="failed",
        metadata_tags={"topic": "nil"},
    )
    linked_id = uuid4()
    await KBDocumentRepository(db_session).link_kb_service_document(
        document,
        kb_service_document_id=linked_id,
    )
    await db_session.commit()

    retry_response = await route_client.client.post(
        f"/api/v1/admin/kb/documents/{document.id}/retry"
    )
    delete_response = await route_client.client.delete(
        f"/api/v1/admin/kb/documents/{document.id}"
    )

    assert retry_response.status_code == 200
    assert retry_response.json()["processing_status"] == "uploaded"
    assert kb_provider.retried_document_ids == [str(linked_id)]
    assert delete_response.status_code == 204
    assert kb_provider.deleted_document_ids == [str(linked_id)]
    assert storage.deletes == [document.storage_key]
    assert await db_session.get(KBDocument, document.id) is None


@pytest.mark.asyncio
async def test_kb_upload_rejects_unknown_tag_slug(route_client, db_session) -> None:
    admin = await _admin_user(db_session)
    route_client.authenticate_as(admin)
    _override_external_providers(route_client)
    collections_response = await route_client.client.get("/api/v1/admin/kb/collections")
    collection = next(
        item for item in collections_response.json() if item["slug"] == "compliance"
    )

    response = await route_client.client.post(
        "/api/v1/admin/kb/documents",
        json={
            "filename": "nil-handbook.pdf",
            "content_type": "application/pdf",
            "size_bytes": 10,
            "collection_id": collection["id"],
            "tag_slugs": ["made-up-tag"],
        },
        headers={"X-Request-ID": "req-kb-array"},
    )

    assert response.status_code == 400
    assert response.json()["error"]["code"] == "VALIDATION_ERROR"
    assert response.json()["error"]["details"]["request_id"] == "req-kb-array"


@pytest.mark.asyncio
async def test_kb_upload_openapi_documents_use_json_direct_upload(
    route_client,
) -> None:
    response = await route_client.client.get("/openapi.json")

    assert response.status_code == 200
    upload_properties = response.json()["components"]["schemas"][
        "KBDocumentUploadRequest"
    ]["properties"]
    upload_response_properties = response.json()["components"]["schemas"][
        "KBDocumentUploadRequestResponse"
    ]["properties"]
    assert "collection_id" in upload_properties
    assert "tag_slugs" in upload_properties
    assert "metadata_tags" not in upload_properties
    assert "filename" in upload_properties
    assert "content_type" in upload_properties
    assert "size_bytes" in upload_properties
    assert "document" in upload_response_properties
    assert "upload" in upload_response_properties
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
    collections_response = await route_client.client.get("/api/v1/admin/kb/collections")
    collection = next(
        item for item in collections_response.json() if item["slug"] == "compliance"
    )

    response = await route_client.client.post(
        "/api/v1/admin/kb/documents",
        json={
            "filename": "notes.txt",
            "content_type": "text/plain",
            "size_bytes": 5,
            "collection_id": collection["id"],
        },
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
