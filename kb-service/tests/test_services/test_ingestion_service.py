from __future__ import annotations

import asyncio
from dataclasses import dataclass
from typing import Any
from uuid import UUID
from uuid import uuid4

import pytest
from fastapi import HTTPException

import app.services.ingestion_service as ingestion_service
import app.workers.tasks as tasks
from app.schemas.ingest import IngestConversationFileRequest, IngestDocumentRequest
from app.services.ingestion_service import (
    _dedupe_md5_for_ingest_request,
    _metadata_from_ingest_request,
    _metadata_with_organization,
)


def test_metadata_with_organization_stamps_missing_scope() -> None:
    organization_id = uuid4()

    metadata = _metadata_with_organization(
        {"source_title": "NIL Handbook"},
        organization_id=organization_id,
    )

    assert metadata["organization_id"] == str(organization_id)
    assert metadata["source_title"] == "NIL Handbook"


def test_metadata_with_organization_rejects_conflicting_scope() -> None:
    organization_id = uuid4()

    with pytest.raises(HTTPException) as exc_info:
        _metadata_with_organization(
            {"organization_id": str(uuid4())},
            organization_id=organization_id,
        )

    assert exc_info.value.status_code == 400
    assert "organization_id" in str(exc_info.value.detail)


def test_ingest_metadata_normalizes_admin_documents_as_official_without_priority() -> None:
    request = IngestDocumentRequest(
        organization_id=uuid4(),
        playbook_document_id=uuid4(),
        configuration_id=uuid4(),
        source_uri="s3://bucket/nil.pdf",
        filename="nil.pdf",
        content_type="application/pdf",
        size_bytes=100,
        source_title="NIL Handbook",
        is_official=False,
        priority=10,
        metadata_tags={"topic": "nil"},
    )

    metadata = _metadata_from_ingest_request(request)

    assert metadata["is_official"] is True
    assert metadata["priority"] == 0
    assert metadata["metadata_tags"] == {"topic": "nil"}


def test_ingest_metadata_disables_webhook_when_url_is_omitted() -> None:
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

    metadata = _metadata_from_ingest_request(request)

    assert metadata["webhook_enabled"] is False
    assert metadata["status_webhook_url"] is None


def test_ingest_metadata_enables_webhook_when_url_is_supplied() -> None:
    request = IngestDocumentRequest(
        organization_id=uuid4(),
        playbook_document_id=uuid4(),
        configuration_id=uuid4(),
        source_uri="s3://bucket/nil.pdf",
        filename="nil.pdf",
        content_type="application/pdf",
        size_bytes=100,
        source_title="NIL Handbook",
        status_webhook_url="http://backend.test/api/v1/kb/webhook",
    )

    metadata = _metadata_from_ingest_request(request)

    assert metadata["webhook_enabled"] is True
    assert metadata["status_webhook_url"] == "http://backend.test/api/v1/kb/webhook"


def test_ingest_metadata_stamps_conversation_file_private_scope_without_source_uri() -> None:
    request = IngestConversationFileRequest(
        organization_id=uuid4(),
        conversation_id=uuid4(),
        conversation_file_id=uuid4(),
        configuration_id=uuid4(),
        source_uri="https://storage.test/contract.pdf?signature=secret",
        filename="contract.pdf",
        content_type="application/pdf",
        size_bytes=100,
        source_title="Contract",
    )

    metadata = _metadata_from_ingest_request(request)

    assert metadata["source_type"] == "conversation_file"
    assert metadata["organization_id"] == str(request.organization_id)
    assert metadata["conversation_id"] == str(request.conversation_id)
    assert metadata["conversation_file_id"] == str(request.conversation_file_id)
    assert metadata["visibility_policy"] == {"scope": "conversation"}
    assert "playbook_document_id" not in metadata
    assert "source_uri" not in metadata
    assert "signature=secret" not in str(metadata)


def test_ingest_metadata_rejects_conversation_file_without_conversation_visibility() -> None:
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
        visibility_policy={"scope": "all_athletes"},
    )

    with pytest.raises(HTTPException) as exc_info:
        _metadata_from_ingest_request(request)

    assert exc_info.value.status_code == 400
    assert "visibility_policy.scope" in str(exc_info.value.detail)


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

    assert _dedupe_md5_for_ingest_request(admin_request, raw_md5) == raw_md5
    scoped = _dedupe_md5_for_ingest_request(file_request, raw_md5)
    assert scoped != raw_md5
    assert len(scoped) == 32


def test_dispatch_pipeline_inserts_summary_stage(monkeypatch) -> None:
    order: list[str] = []

    class FakeSignature:
        def __init__(self, name: str) -> None:
            self.name = name

        def __or__(self, other: "FakeSignature") -> "FakePipeline":
            return FakePipeline([self, other])

    class FakePipeline:
        def __init__(self, items: list[FakeSignature]) -> None:
            self.items = items

        def __or__(self, other: FakeSignature) -> "FakePipeline":
            self.items.append(other)
            return self

        def apply_async(self):
            order.extend(item.name for item in self.items)
            return type("Result", (), {"id": "pipeline-task"})()

    class FakeTask:
        def __init__(self, name: str) -> None:
            self.name = name

        def s(self, *args, **kwargs) -> FakeSignature:
            return FakeSignature(self.name)

    async def no_root_task_id(self, document_id, root_task_id):
        return None

    monkeypatch.setattr(tasks, "parse_task", FakeTask("parse"), raising=False)
    monkeypatch.setattr(tasks, "chunk_task", FakeTask("chunk"), raising=False)
    monkeypatch.setattr(tasks, "summarize_task", FakeTask("summarize"), raising=False)
    monkeypatch.setattr(tasks, "embed_task", FakeTask("embed"), raising=False)

    service = ingestion_service.IngestionService.__new__(
        ingestion_service.IngestionService
    )
    service._log_repo = type(
        "LogRepo",
        (),
        {"set_root_task_id": no_root_task_id},
    )()

    task_id = asyncio.run(
        service._dispatch_pipeline(
            uuid4(),
            type("Config", (), {"id": uuid4()})(),
            "kb/originals/doc.pdf",
            "doc.pdf",
            {"source_type": "admin_upload"},
        )
    )

    assert task_id == "pipeline-task"
    assert order == ["parse", "chunk", "summarize", "embed"]


@dataclass
class _RetryDocument:
    id: UUID
    configuration_id: UUID
    s3_key: str
    name: str
    metadata_: dict[str, Any]


@dataclass
class _RetryConfig:
    id: UUID


class _RetryDocumentRepo:
    def __init__(self, document: _RetryDocument) -> None:
        self.document = document
        self.status_updates: list[tuple[UUID, str]] = []

    async def get(self, document_id: UUID) -> _RetryDocument | None:
        return self.document if document_id == self.document.id else None

    async def update_status(self, document_id: UUID, status: str) -> None:
        self.status_updates.append((document_id, status))


class _RetryConfigRepo:
    def __init__(self, config: _RetryConfig) -> None:
        self.config = config

    async def get(self, config_id: UUID) -> _RetryConfig | None:
        return self.config if config_id == self.config.id else None


class _RetryLogRepo:
    def __init__(self) -> None:
        self.created: list[UUID] = []

    async def get_by_document(self, document_id: UUID) -> object | None:
        return None

    async def create(self, document_id: UUID) -> None:
        self.created.append(document_id)


class _RetryVectorRepo:
    def __init__(self) -> None:
        self.deleted: list[UUID] = []

    async def delete_document_embeddings(self, document_id: UUID) -> int:
        self.deleted.append(document_id)
        return 4


@pytest.mark.asyncio
async def test_retry_document_preserves_conversation_file_identity_and_deletes_vectors() -> None:
    document_id = uuid4()
    config = _RetryConfig(id=uuid4())
    conversation_id = uuid4()
    conversation_file_id = uuid4()
    document = _RetryDocument(
        id=document_id,
        configuration_id=config.id,
        s3_key="conversation-files/originals/contract.pdf",
        name="contract.pdf",
        metadata_={
            "source_type": "conversation_file",
            "organization_id": str(uuid4()),
            "conversation_id": str(conversation_id),
            "conversation_file_id": str(conversation_file_id),
            "visibility_policy": {"scope": "conversation"},
        },
    )
    service = ingestion_service.IngestionService.__new__(
        ingestion_service.IngestionService
    )
    service._doc_repo = _RetryDocumentRepo(document)
    service._config_repo = _RetryConfigRepo(config)
    service._log_repo = _RetryLogRepo()
    service._vector_repo = _RetryVectorRepo()
    dispatched: dict[str, Any] = {}

    async def fake_dispatch_pipeline(
        document_id: UUID,
        config: _RetryConfig,
        s3_key: str,
        filename: str,
        metadata: dict[str, Any],
    ) -> str:
        dispatched.update(
            {
                "document_id": document_id,
                "config_id": config.id,
                "s3_key": s3_key,
                "filename": filename,
                "metadata": metadata,
            }
        )
        return "retry-task-id"

    service._dispatch_pipeline = fake_dispatch_pipeline

    response = await service.retry_document(document_id)

    assert service._vector_repo.deleted == [document_id]
    assert service._doc_repo.status_updates == [(document_id, "pending")]
    assert service._log_repo.created == [document_id]
    assert dispatched == {
        "document_id": document_id,
        "config_id": config.id,
        "s3_key": "conversation-files/originals/contract.pdf",
        "filename": "contract.pdf",
        "metadata": document.metadata_,
    }
    assert response.kb_service_document_id == document_id
    assert response.source_type == "conversation_file"
    assert response.conversation_id == conversation_id
    assert response.conversation_file_id == conversation_file_id
    assert response.task_id == "retry-task-id"
    assert response.status == "pending"
