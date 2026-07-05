from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID, uuid4

import pytest

import app.infrastructure.db.session as db_session
import app.repositories.document_repo as document_repo
import app.repositories.ingestion_log_repo as ingestion_log_repo
import app.repositories.vector_repo as vector_repo
import app.workers.rate_limiter as rate_limiter
import app.workers.tasks.embedding as embedding_tasks
from app.workers.state import worker_state


@dataclass
class _FakeDocument:
    id: UUID
    status: str = "chunking"


class _FakeSession:
    async def __aenter__(self) -> "_FakeSession":
        return self

    async def __aexit__(self, exc_type, exc, tb) -> None:
        return None


class _FakeSessionFactory:
    def __call__(self) -> _FakeSession:
        return _FakeSession()


class _DocumentDeletedAfterEmbeddingRepo:
    def __init__(self, session: _FakeSession, document: _FakeDocument) -> None:
        self.document = document
        self.get_calls = 0
        self.status_updates: list[tuple[UUID, str]] = []

    async def get(self, document_id: UUID) -> _FakeDocument | None:
        self.get_calls += 1
        if self.get_calls == 1:
            return self.document
        return None

    async def update_status(self, document_id: UUID, status: str) -> None:
        self.status_updates.append((document_id, status))


class _FakeIngestionLogRepo:
    def __init__(self, session: _FakeSession) -> None:
        self.stage_updates: list[dict] = []

    async def update_stage(
        self,
        document_id: UUID,
        *,
        stage: str,
        task_id: str | None = None,
        status: str,
        error_message: str | None = None,
    ) -> None:
        self.stage_updates.append(
            {
                "document_id": document_id,
                "stage": stage,
                "task_id": task_id,
                "status": status,
                "error_message": error_message,
            }
        )


class _FakeVectorRepo:
    def __init__(self, pg_engine: object) -> None:
        self.deleted: list[UUID] = []
        self.inserted: list[UUID] = []

    def delete_document_embeddings(self, document_id: UUID) -> int:
        self.deleted.append(document_id)
        return 1

    def insert_batch_embeddings(self, *, document_id: UUID, **kwargs) -> int:
        self.inserted.append(document_id)
        return 1


class _FakeEmbedClient:
    def embed(self, texts: list[str]) -> list[list[float]]:
        return [[0.1, 0.2, 0.3] for _text in texts]


def test_embed_batch_skips_vector_insert_when_document_deleted_mid_task(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    document = _FakeDocument(id=uuid4())
    doc_repo_holder: dict[str, _DocumentDeletedAfterEmbeddingRepo] = {}
    log_repo_holder: dict[str, _FakeIngestionLogRepo] = {}
    vector_repo_holder: dict[str, _FakeVectorRepo] = {}
    progress_calls: list[str] = []

    def build_doc_repo(session: _FakeSession) -> _DocumentDeletedAfterEmbeddingRepo:
        repo = _DocumentDeletedAfterEmbeddingRepo(session, document)
        doc_repo_holder["repo"] = repo
        return repo

    def build_log_repo(session: _FakeSession) -> _FakeIngestionLogRepo:
        repo = _FakeIngestionLogRepo(session)
        log_repo_holder["repo"] = repo
        return repo

    def build_vector_repo(pg_engine: object) -> _FakeVectorRepo:
        repo = _FakeVectorRepo(pg_engine)
        vector_repo_holder["repo"] = repo
        return repo

    monkeypatch.setattr(db_session, "get_session_factory", lambda: _FakeSessionFactory())
    monkeypatch.setattr(document_repo, "DocumentRepository", build_doc_repo)
    monkeypatch.setattr(ingestion_log_repo, "IngestionLogRepository", build_log_repo)
    monkeypatch.setattr(vector_repo, "VectorRepository", build_vector_repo)
    monkeypatch.setattr(rate_limiter, "acquire_embed_slot", lambda: None)
    monkeypatch.setattr(rate_limiter, "release_embed_slot", lambda: None)
    monkeypatch.setattr(worker_state, "_embed_client_factory", lambda: _FakeEmbedClient())
    monkeypatch.setattr(worker_state._embed_clients, "client", None, raising=False)
    monkeypatch.setattr(worker_state, "pg_engine", object())
    monkeypatch.setattr(
        embedding_tasks,
        "_load_chunk_slice_from_s3",
        lambda document_id, chunk_start, chunk_end: [
            {"text": "Athletes must disclose endorsement deals."}
        ],
    )
    monkeypatch.setattr(
        embedding_tasks,
        "increment_embed_progress",
        lambda document_id: progress_calls.append(document_id) or 1,
    )

    result = embedding_tasks.embed_batch_task.run(
        document_id=str(document.id),
        config_id=str(uuid4()),
        batch_index=0,
        chunk_start=0,
        chunk_end=1,
        total_batches=1,
    )

    assert result["status"] == "skipped_deleted_document"
    assert vector_repo_holder["repo"].deleted == [document.id]
    assert vector_repo_holder["repo"].inserted == []
    assert progress_calls == []
    assert doc_repo_holder["repo"].status_updates == [(document.id, "embedding")]
    assert log_repo_holder["repo"].stage_updates[0]["status"] == "STARTED"
