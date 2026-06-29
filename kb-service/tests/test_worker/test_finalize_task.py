from __future__ import annotations

from uuid import UUID, uuid4

import pytest

import app.infrastructure.db.session as db_session
import app.repositories.document_repo as document_repo
import app.repositories.ingestion_log_repo as ingestion_log_repo
import app.repositories.vector_repo as vector_repo
import app.workers.tasks.finalize as finalize_tasks
from app.workers.state import worker_state


class _FakeSession:
    async def __aenter__(self) -> "_FakeSession":
        return self

    async def __aexit__(self, exc_type, exc, tb) -> None:
        return None


class _FakeSessionFactory:
    def __call__(self) -> _FakeSession:
        return _FakeSession()


class _MissingDocumentRepo:
    def __init__(self, session: _FakeSession) -> None:
        self.session = session

    async def get(self, document_id: UUID) -> None:
        return None


class _FakeIngestionLogRepo:
    def __init__(self, session: _FakeSession) -> None:
        self.session = session

    async def get_by_document(self, document_id: UUID) -> None:
        return None


class _FakeVectorRepo:
    def __init__(self, pg_engine: object) -> None:
        self.deleted: list[UUID] = []

    def delete_document_embeddings(self, document_id: UUID) -> int:
        self.deleted.append(document_id)
        return 2


def test_load_vector_task_noops_stale_deleted_document_before_defer_or_reissue(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    document_id = uuid4()
    vector_repo_holder: dict[str, _FakeVectorRepo] = {}
    deleted_staging: list[tuple[str, str]] = []
    reset_progress: list[str] = []

    def build_vector_repo(pg_engine: object) -> _FakeVectorRepo:
        repo = _FakeVectorRepo(pg_engine)
        vector_repo_holder["repo"] = repo
        return repo

    monkeypatch.setattr(db_session, "get_session_factory", lambda: _FakeSessionFactory())
    monkeypatch.setattr(document_repo, "DocumentRepository", _MissingDocumentRepo)
    monkeypatch.setattr(ingestion_log_repo, "IngestionLogRepository", _FakeIngestionLogRepo)
    monkeypatch.setattr(vector_repo, "VectorRepository", build_vector_repo)
    monkeypatch.setattr(worker_state, "pg_engine", object())
    monkeypatch.setattr(finalize_tasks, "get_embed_progress", lambda document_id: 0)
    monkeypatch.setattr(
        finalize_tasks,
        "_count_chunks_in_s3",
        lambda document_id: (_ for _ in ()).throw(
            AssertionError("deleted document must not read chunk staging")
        ),
    )
    monkeypatch.setattr(
        finalize_tasks,
        "_delete_pages_staging",
        lambda doc_id: deleted_staging.append(("pages", doc_id)),
        raising=False,
    )
    monkeypatch.setattr(
        finalize_tasks,
        "_delete_staging_file",
        lambda doc_id: deleted_staging.append(("chunks", doc_id)),
    )
    monkeypatch.setattr(
        finalize_tasks,
        "reset_embed_progress",
        lambda doc_id: reset_progress.append(doc_id),
    )

    result = finalize_tasks.load_vector_task.run(
        document_id=str(document_id),
        config_id=str(uuid4()),
        expected_total_batches=3,
    )

    assert result == {
        "document_id": str(document_id),
        "skipped": True,
        "reason": "deleted_document",
    }
    assert vector_repo_holder["repo"].deleted == [document_id]
    assert deleted_staging == [
        ("pages", str(document_id)),
        ("chunks", str(document_id)),
    ]
    assert reset_progress == [str(document_id)]
