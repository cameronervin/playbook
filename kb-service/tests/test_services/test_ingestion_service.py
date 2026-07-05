from __future__ import annotations

import asyncio
from dataclasses import dataclass
from datetime import date
from typing import Any
from uuid import UUID, uuid4

import pytest
from fastapi import HTTPException

import app.services.ingestion as ingestion_service
import app.services.ingestion.service as ingestion_service_module
import app.workers.tasks as tasks
from app.schemas.ingest import (
    DocumentMetadataRefreshRequest,
    IngestConversationFileRequest,
    IngestDocumentRequest,
)


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
    def __init__(self, existing: object | None = None) -> None:
        self.existing = existing
        self.created: list[UUID] = []
        self.reset: list[UUID] = []

    async def get_by_document(self, document_id: UUID) -> object | None:
        return self.existing

    async def create(self, document_id: UUID) -> None:
        self.created.append(document_id)

    async def reset_for_retry(self, document_id: UUID) -> None:
        self.reset.append(document_id)


class _RetryVectorRepo:
    def __init__(self) -> None:
        self.deleted: list[UUID] = []

    async def delete_document_embeddings(self, document_id: UUID) -> int:
        self.deleted.append(document_id)
        return 4


@dataclass
class _RefreshDocument:
    id: UUID
    metadata_: dict[str, Any]


class _RefreshDocumentRepo:
    def __init__(self, document: _RefreshDocument | None) -> None:
        self.document = document
        self.updated: list[tuple[UUID, dict[str, Any]]] = []

    async def get(self, document_id: UUID) -> _RefreshDocument | None:
        if self.document and self.document.id == document_id:
            return self.document
        return None

    async def update_metadata(
        self,
        document_id: UUID,
        metadata: dict[str, Any],
    ) -> _RefreshDocument | None:
        self.updated.append((document_id, metadata))
        if self.document is None:
            return None
        self.document.metadata_ = metadata
        return self.document


class _RefreshVectorRepo:
    def __init__(self) -> None:
        self.updated: list[tuple[UUID, dict[str, Any]]] = []
        self.stale_keys: list[set[str]] = []

    async def refresh_document_metadata(
        self,
        document_id: UUID,
        metadata: dict[str, Any],
        stale_metadata_keys: set[str] | None = None,
    ) -> int:
        self.updated.append((document_id, metadata))
        self.stale_keys.append(set(stale_metadata_keys or set()))
        return 5


@dataclass
class _DeleteDocument:
    id: UUID
    s3_key: str | None


class _DeleteDocumentRepo:
    def __init__(self, document: _DeleteDocument | None) -> None:
        self.document = document
        self.deleted: list[UUID] = []

    async def get(self, document_id: UUID) -> _DeleteDocument | None:
        if self.document and document_id == self.document.id:
            return self.document
        return None

    async def delete(self, document_id: UUID) -> bool:
        self.deleted.append(document_id)
        return True


class _DeleteVectorRepo:
    def __init__(self) -> None:
        self.deleted: list[UUID] = []

    async def delete_document_embeddings(self, document_id: UUID) -> int:
        self.deleted.append(document_id)
        return 3


@dataclass
class _StartConfig:
    id: UUID


@dataclass
class _StartDocument:
    id: UUID
    configuration_id: UUID
    s3_key: str
    name: str
    md5: str
    status: str
    metadata_: dict[str, Any]


class _StartConfigRepo:
    def __init__(self, config: _StartConfig) -> None:
        self.config = config

    async def get(self, config_id: UUID) -> _StartConfig | None:
        return self.config if config_id == self.config.id else None


@dataclass
class _StartIngestionLog:
    pipeline_task_id: str | None


class _StartLogRepo:
    def __init__(self, task_id: str | None = "existing-task-id") -> None:
        self.task_id = task_id
        self.created: list[UUID] = []

    async def get_by_document(self, document_id: UUID) -> _StartIngestionLog | None:
        return _StartIngestionLog(self.task_id) if self.task_id is not None else None

    async def create(self, document_id: UUID) -> None:
        self.created.append(document_id)


class _StartDocumentRepo:
    def __init__(
        self,
        *,
        source_identity_document: _StartDocument | None = None,
        md5_document: _StartDocument | None = None,
    ) -> None:
        self.source_identity_document = source_identity_document
        self.md5_document = md5_document
        self.created: list[dict[str, Any]] = []
        self.deleted: list[UUID] = []
        self.updated: list[tuple[UUID, dict[str, Any]]] = []

    async def get_by_admin_source_identity(
        self,
        *,
        configuration_id: UUID,
        organization_id: UUID,
        playbook_document_id: UUID,
    ) -> _StartDocument | None:
        return self.source_identity_document

    async def get_by_conversation_file_source_identity(
        self,
        *,
        configuration_id: UUID,
        organization_id: UUID,
        conversation_id: UUID,
        conversation_file_id: UUID,
    ) -> _StartDocument | None:
        return self.source_identity_document

    async def get_by_config_and_md5(
        self,
        configuration_id: UUID,
        md5: str,
    ) -> _StartDocument | None:
        return self.md5_document

    async def create(self, **kwargs: Any) -> _StartDocument:
        self.created.append(kwargs)
        return _StartDocument(
            id=kwargs["document_id"],
            configuration_id=kwargs["configuration_id"],
            s3_key=kwargs["s3_key"],
            name=kwargs["name"],
            md5=kwargs["md5"],
            status="pending",
            metadata_=kwargs["metadata"],
        )

    async def delete(self, document_id: UUID) -> bool:
        self.deleted.append(document_id)
        return True

    async def update_metadata(
        self,
        document_id: UUID,
        metadata: dict[str, Any],
    ) -> _StartDocument | None:
        self.updated.append((document_id, metadata))
        for document in (self.source_identity_document, self.md5_document):
            if document and document.id == document_id:
                document.metadata_ = metadata
                return document
        return None


class _StartVectorRepo:
    def __init__(self) -> None:
        self.deleted: list[UUID] = []
        self.updated: list[tuple[UUID, dict[str, Any]]] = []
        self.stale_keys: list[set[str]] = []

    async def delete_document_embeddings(self, document_id: UUID) -> int:
        self.deleted.append(document_id)
        return 0

    async def refresh_document_metadata(
        self,
        document_id: UUID,
        metadata: dict[str, Any],
        stale_metadata_keys: set[str] | None = None,
    ) -> int:
        self.updated.append((document_id, metadata))
        self.stale_keys.append(set(stale_metadata_keys or set()))
        return 2


def _service_for_start_ingest(
    *,
    config: _StartConfig,
    document_repo: _StartDocumentRepo,
    log_repo: _StartLogRepo | None = None,
) -> ingestion_service.IngestionService:
    service = ingestion_service.IngestionService.__new__(
        ingestion_service.IngestionService
    )
    service._config_repo = _StartConfigRepo(config)
    service._doc_repo = document_repo
    service._log_repo = log_repo or _StartLogRepo()
    service._vector_repo = _StartVectorRepo()
    service._IN_PROGRESS_STATUSES = ingestion_service.IngestionService._IN_PROGRESS_STATUSES

    async def fail_size_check(s3_key: str) -> None:
        raise AssertionError("duplicate source identity must not HEAD storage")

    async def fail_md5(s3_key: str) -> str:
        raise AssertionError("duplicate source identity must not download storage")

    async def fail_dispatch(*args: Any, **kwargs: Any) -> str:
        raise AssertionError("duplicate source identity must not dispatch ingestion")

    service._enforce_max_size = fail_size_check
    service._compute_s3_object_md5 = fail_md5
    service._dispatch_pipeline = fail_dispatch
    return service


def _admin_request(
    *,
    organization_id: UUID,
    playbook_document_id: UUID,
    configuration_id: UUID,
    source_date: date | None = None,
    metadata_tags: dict[str, Any] | None = None,
    visibility_policy: dict[str, Any] | None = None,
) -> IngestDocumentRequest:
    return IngestDocumentRequest(
        organization_id=organization_id,
        playbook_document_id=playbook_document_id,
        configuration_id=configuration_id,
        source_uri="https://storage.test/bucket/nil.pdf?signature=secret",
        filename="nil.pdf",
        content_type="application/pdf",
        size_bytes=100,
        source_title="NIL Handbook",
        source_date=source_date,
        visibility_policy=visibility_policy or {"scope": "all_athletes"},
        metadata_tags=metadata_tags or {},
    )


def _conversation_file_request(
    *,
    organization_id: UUID,
    conversation_id: UUID,
    conversation_file_id: UUID,
    configuration_id: UUID,
) -> IngestConversationFileRequest:
    return IngestConversationFileRequest(
        organization_id=organization_id,
        conversation_id=conversation_id,
        conversation_file_id=conversation_file_id,
        configuration_id=configuration_id,
        source_uri="https://storage.test/bucket/contract.pdf?signature=secret",
        filename="contract.pdf",
        content_type="application/pdf",
        size_bytes=100,
        source_title="Contract",
    )


@pytest.mark.asyncio
async def test_delete_document_removes_embeddings_original_and_staging(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    document_id = uuid4()
    service = ingestion_service.IngestionService.__new__(
        ingestion_service.IngestionService
    )
    service._doc_repo = _DeleteDocumentRepo(
        _DeleteDocument(id=document_id, s3_key="kb/originals/nil.docx")
    )
    service._vector_repo = _DeleteVectorRepo()
    deleted_original_keys: list[str] = []
    deleted_staging: list[tuple[str, str]] = []

    monkeypatch.setattr(
        ingestion_service_module,
        "delete_s3_object",
        lambda key: deleted_original_keys.append(key),
    )
    monkeypatch.setattr(
        ingestion_service_module,
        "_delete_pages_staging",
        lambda doc_id: deleted_staging.append(("pages", doc_id)),
        raising=False,
    )
    monkeypatch.setattr(
        ingestion_service_module,
        "_delete_staging_file",
        lambda doc_id: deleted_staging.append(("chunks", doc_id)),
        raising=False,
    )

    await service.delete_document(document_id)

    assert service._vector_repo.deleted == [document_id]
    assert service._doc_repo.deleted == [document_id]
    assert deleted_original_keys == ["kb/originals/nil.docx"]
    assert deleted_staging == [
        ("pages", str(document_id)),
        ("chunks", str(document_id)),
    ]


@pytest.mark.asyncio
async def test_start_ingest_duplicate_admin_returns_existing_without_side_effects() -> None:
    config = _StartConfig(id=uuid4())
    organization_id = uuid4()
    playbook_document_id = uuid4()
    existing = _StartDocument(
        id=uuid4(),
        configuration_id=config.id,
        s3_key="kb/originals/nil.pdf",
        name="nil.pdf",
        md5="a" * 32,
        status="success",
        metadata_={
            "source_type": "admin_upload",
            "organization_id": str(organization_id),
            "playbook_document_id": str(playbook_document_id),
        },
    )
    document_repo = _StartDocumentRepo(source_identity_document=existing)
    service = _service_for_start_ingest(config=config, document_repo=document_repo)

    response = await service.start_ingest(
        _admin_request(
            organization_id=organization_id,
            playbook_document_id=playbook_document_id,
            configuration_id=config.id,
        )
    )

    assert response.kb_service_document_id == existing.id
    assert response.playbook_document_id == playbook_document_id
    assert response.task_id is None
    assert response.status == "success"
    assert document_repo.created == []
    assert document_repo.deleted == []


@pytest.mark.asyncio
async def test_start_ingest_duplicate_admin_refreshes_existing_metadata() -> None:
    config = _StartConfig(id=uuid4())
    organization_id = uuid4()
    playbook_document_id = uuid4()
    existing = _StartDocument(
        id=uuid4(),
        configuration_id=config.id,
        s3_key="kb/originals/nil.pdf",
        name="nil.pdf",
        md5="a" * 32,
        status="success",
        metadata_={
            "source_type": "admin_upload",
            "organization_id": str(organization_id),
            "playbook_document_id": str(playbook_document_id),
            "source_title": "NIL Handbook",
            "source_date": "2026-01-01",
            "is_official": True,
            "priority": 0,
            "visibility_policy": {"scope": "all_athletes"},
            "metadata_tags": {
                "collection": "Old",
                "tag_slugs": ["old"],
                "legacy_topic": "stale",
            },
            "collection": "Old",
            "tag_slugs": ["old"],
            "legacy_topic": "stale",
            "raw_content_md5": "a" * 32,
        },
    )
    document_repo = _StartDocumentRepo(source_identity_document=existing)
    service = _service_for_start_ingest(config=config, document_repo=document_repo)
    expected_metadata = {
        "source_type": "admin_upload",
        "organization_id": str(organization_id),
        "playbook_document_id": str(playbook_document_id),
        "source_title": "NIL Handbook",
        "source_date": "2026-02-01",
        "is_official": True,
        "priority": 0,
        "visibility_policy": {"scope": "all_athletes"},
        "metadata_tags": {
            "collection": "Compliance",
            "tag_slugs": ["compliance"],
            "tags": ["Compliance"],
        },
        "collection": "Compliance",
        "tag_slugs": ["compliance"],
        "tags": ["Compliance"],
        "raw_content_md5": "a" * 32,
    }

    response = await service.start_ingest(
        _admin_request(
            organization_id=organization_id,
            playbook_document_id=playbook_document_id,
            configuration_id=config.id,
            source_date=date(2026, 2, 1),
            metadata_tags={
                "collection": "Compliance",
                "tag_slugs": ["compliance"],
                "tags": ["Compliance"],
            },
        )
    )

    assert response.kb_service_document_id == existing.id
    assert response.playbook_document_id == playbook_document_id
    assert document_repo.updated == [(existing.id, expected_metadata)]
    assert service._vector_repo.updated == [(existing.id, expected_metadata)]
    assert "legacy_topic" in service._vector_repo.stale_keys[0]
    assert document_repo.created == []
    assert document_repo.deleted == []


@pytest.mark.asyncio
async def test_start_ingest_duplicate_conversation_file_returns_private_identity() -> None:
    config = _StartConfig(id=uuid4())
    organization_id = uuid4()
    conversation_id = uuid4()
    conversation_file_id = uuid4()
    existing = _StartDocument(
        id=uuid4(),
        configuration_id=config.id,
        s3_key="conversation-files/originals/contract.pdf",
        name="contract.pdf",
        md5="b" * 32,
        status="pending",
        metadata_={
            "source_type": "conversation_file",
            "organization_id": str(organization_id),
            "conversation_id": str(conversation_id),
            "conversation_file_id": str(conversation_file_id),
            "visibility_policy": {"scope": "conversation"},
        },
    )
    service = _service_for_start_ingest(
        config=config,
        document_repo=_StartDocumentRepo(source_identity_document=existing),
        log_repo=_StartLogRepo(task_id="private-task-id"),
    )

    response = await service.start_ingest(
        _conversation_file_request(
            organization_id=organization_id,
            conversation_id=conversation_id,
            conversation_file_id=conversation_file_id,
            configuration_id=config.id,
        )
    )

    assert response.kb_service_document_id == existing.id
    assert response.conversation_id == conversation_id
    assert response.conversation_file_id == conversation_file_id
    assert response.task_id == "private-task-id"
    assert response.status == "pending"


@pytest.mark.asyncio
async def test_start_ingest_failed_duplicate_is_not_implicitly_retried() -> None:
    config = _StartConfig(id=uuid4())
    organization_id = uuid4()
    playbook_document_id = uuid4()
    existing = _StartDocument(
        id=uuid4(),
        configuration_id=config.id,
        s3_key="kb/originals/nil.pdf",
        name="nil.pdf",
        md5="c" * 32,
        status="failed",
        metadata_={
            "source_type": "admin_upload",
            "organization_id": str(organization_id),
            "playbook_document_id": str(playbook_document_id),
        },
    )
    service = _service_for_start_ingest(
        config=config,
        document_repo=_StartDocumentRepo(source_identity_document=existing),
        log_repo=_StartLogRepo(task_id="old-task-id"),
    )

    response = await service.start_ingest(
        _admin_request(
            organization_id=organization_id,
            playbook_document_id=playbook_document_id,
            configuration_id=config.id,
        )
    )

    assert response.kb_service_document_id == existing.id
    assert response.task_id is None
    assert response.status == "failed"


@pytest.mark.asyncio
async def test_start_ingest_same_content_different_source_identity_returns_conflict() -> None:
    config = _StartConfig(id=uuid4())
    organization_id = uuid4()
    existing = _StartDocument(
        id=uuid4(),
        configuration_id=config.id,
        s3_key="kb/originals/existing.pdf",
        name="existing.pdf",
        md5="d" * 32,
        status="success",
        metadata_={
            "source_type": "admin_upload",
            "organization_id": str(organization_id),
            "playbook_document_id": str(uuid4()),
        },
    )
    document_repo = _StartDocumentRepo(md5_document=existing)
    service = _service_for_start_ingest(config=config, document_repo=document_repo)

    async def no_size_check(s3_key: str) -> None:
        return None

    async def same_md5(s3_key: str) -> str:
        return existing.md5

    service._enforce_max_size = no_size_check
    service._compute_s3_object_md5 = same_md5

    with pytest.raises(HTTPException) as exc_info:
        await service.start_ingest(
            _admin_request(
                organization_id=organization_id,
                playbook_document_id=uuid4(),
                configuration_id=config.id,
            )
        )

    assert exc_info.value.status_code == 409
    assert "trusted source identity" in str(exc_info.value.detail)
    assert document_repo.deleted == []


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


@pytest.mark.asyncio
async def test_retry_document_resets_existing_ingestion_log_before_dispatch() -> None:
    document_id = uuid4()
    config = _RetryConfig(id=uuid4())
    document = _RetryDocument(
        id=document_id,
        configuration_id=config.id,
        s3_key="kb/originals/policy.docx",
        name="policy.docx",
        metadata_={
            "source_type": "admin_upload",
            "organization_id": str(uuid4()),
            "playbook_document_id": str(uuid4()),
        },
    )
    service = ingestion_service.IngestionService.__new__(
        ingestion_service.IngestionService
    )
    service._doc_repo = _RetryDocumentRepo(document)
    service._config_repo = _RetryConfigRepo(config)
    service._log_repo = _RetryLogRepo(existing=object())
    service._vector_repo = _RetryVectorRepo()
    dispatched: dict[str, Any] = {}

    async def fake_dispatch_pipeline(
        document_id: UUID,
        config: _RetryConfig,
        s3_key: str,
        filename: str,
        metadata: dict[str, Any],
    ) -> str:
        dispatched["document_id"] = document_id
        return "retry-task-id"

    service._dispatch_pipeline = fake_dispatch_pipeline

    response = await service.retry_document(document_id)

    assert service._vector_repo.deleted == [document_id]
    assert service._doc_repo.status_updates == [(document_id, "pending")]
    assert service._log_repo.created == []
    assert service._log_repo.reset == [document_id]
    assert dispatched["document_id"] == document_id
    assert response.task_id == "retry-task-id"


@pytest.mark.asyncio
async def test_refresh_document_metadata_updates_document_and_vectors() -> None:
    document_id = uuid4()
    playbook_document_id = uuid4()
    document = _RefreshDocument(
        id=document_id,
        metadata_={
            "source_type": "admin_upload",
            "organization_id": str(uuid4()),
            "playbook_document_id": str(playbook_document_id),
            "source_title": "NIL Handbook",
            "source_date": "2026-01-15",
            "is_official": True,
            "priority": 0,
            "visibility_policy": {"scope": "all_athletes"},
            "metadata_tags": {"collection": "old", "legacy_topic": "stale"},
            "collection": "old",
            "legacy_topic": "stale",
            "raw_content_md5": "abc123",
        },
    )
    service = ingestion_service.IngestionService.__new__(
        ingestion_service.IngestionService
    )
    service._doc_repo = _RefreshDocumentRepo(document)
    service._vector_repo = _RefreshVectorRepo()

    response = await service.refresh_document_metadata(
        document_id,
        DocumentMetadataRefreshRequest(
            source_date="2026-02-01",
            is_official=False,
            priority=99,
            visibility_policy={"scope": "all_athletes"},
            metadata_tags={
                "collection": "compliance",
                "tag_slugs": ["compliance"],
                "tags": ["Compliance"],
            },
        ),
    )

    expected_metadata = {
        "source_type": "admin_upload",
        "organization_id": document.metadata_["organization_id"],
        "playbook_document_id": str(playbook_document_id),
        "source_title": "NIL Handbook",
        "source_date": "2026-02-01",
        "is_official": True,
        "priority": 0,
        "visibility_policy": {"scope": "all_athletes"},
        "metadata_tags": {
            "collection": "compliance",
            "tag_slugs": ["compliance"],
            "tags": ["Compliance"],
        },
        "collection": "compliance",
        "tag_slugs": ["compliance"],
        "tags": ["Compliance"],
        "raw_content_md5": "abc123",
    }
    assert service._doc_repo.updated == [(document_id, expected_metadata)]
    assert service._vector_repo.updated == [(document_id, expected_metadata)]
    assert "legacy_topic" in service._vector_repo.stale_keys[0]
    assert response.kb_service_document_id == document_id
    assert response.playbook_document_id == playbook_document_id
    assert response.updated_embedding_count == 5
    assert response.metadata == expected_metadata
