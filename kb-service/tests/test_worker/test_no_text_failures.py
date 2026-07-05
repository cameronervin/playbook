from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID, uuid4

import pytest

import app.infrastructure.db.session as db_session
import app.infrastructure.io.s3_tempfile as s3_tempfile
import app.repositories.document_repo as document_repo
import app.repositories.ingestion_log_repo as ingestion_log_repo
from app.infrastructure.parsers.contracts.errors import (
    NoTextExtractedError,
    ParseWarning,
)
from app.infrastructure.parsers.contracts.models import ParseArtifacts, ParseOutcome
from app.services.ingestion import IngestionService
from app.workers import tasks
import app.workers.tasks.ingest as ingest_tasks
from app.workers.state import worker_state


@dataclass
class _FakeDocument:
    id: UUID
    status: str = "pending"
    updated_at: object | None = None
    metadata_: dict | None = None


@dataclass
class _FakeIngestionLog:
    pipeline_task_id: str | None = "pipeline-task"
    parse_status: str | None = None
    chunk_status: str | None = None
    embed_status: str | None = None
    load_vector_status: str | None = None
    parse_task_id: str | None = None
    chunk_task_id: str | None = None
    embed_task_id: str | None = None
    load_vector_task_id: str | None = None
    error_message: str | None = None
    updated_at: object | None = None


class _FakeSession:
    async def __aenter__(self) -> "_FakeSession":
        return self

    async def __aexit__(self, exc_type, exc, tb) -> None:
        return None


class _FakeSessionFactory:
    def __call__(self) -> _FakeSession:
        return _FakeSession()


class _FakeDocumentRepository:
    def __init__(self, session: _FakeSession, document: _FakeDocument) -> None:
        self.document = document
        self.status_updates: list[tuple[UUID, str]] = []

    async def get(self, document_id: UUID) -> _FakeDocument:
        return self.document

    async def update_status(
        self,
        document_id: UUID,
        status: str,
        error_message: str | None = None,
    ) -> _FakeDocument:
        self.status_updates.append((document_id, status))
        self.document.status = status
        return self.document


class _FakeIngestionLogRepository:
    def __init__(self, session: _FakeSession, log: _FakeIngestionLog) -> None:
        self.log = log
        self.stage_updates: list[dict] = []

    async def get_by_document(self, document_id: UUID) -> _FakeIngestionLog:
        return self.log

    async def update_stage(
        self,
        document_id: UUID,
        *,
        stage: str,
        task_id: str | None = None,
        status: str,
        error_message: str | None = None,
    ) -> _FakeIngestionLog:
        self.stage_updates.append(
            {
                "document_id": document_id,
                "stage": stage,
                "task_id": task_id,
                "status": status,
                "error_message": error_message,
            }
        )
        setattr(self.log, f"{stage}_status", status)
        if task_id:
            setattr(self.log, f"{stage}_task_id", task_id)
        if error_message:
            self.log.error_message = error_message
        return self.log

    async def set_parse_result(self, *args, **kwargs) -> _FakeIngestionLog:
        return self.log


class _FakeTempfile:
    async def __aenter__(self) -> str:
        return "/tmp/no-text.pdf"

    async def __aexit__(self, exc_type, exc, tb) -> None:
        return None


class _BlankOutcomeRouter:
    async def route_path(self, **kwargs) -> ParseOutcome:
        return ParseOutcome(
            text_segments=["   ", "\n"],
            artifacts=ParseArtifacts(),
            selected_parser="FakeParser",
            route="unit_test",
        )


class _LowTextWarningRouter:
    async def route_path(self, **kwargs) -> ParseOutcome:
        raise ParseWarning("Low text output for PDF: scan.pdf")


def _install_fake_repositories(monkeypatch: pytest.MonkeyPatch):
    document = _FakeDocument(id=uuid4(), metadata_={"playbook_document_id": str(uuid4())})
    log = _FakeIngestionLog()
    doc_repo_holder: dict[str, _FakeDocumentRepository] = {}
    log_repo_holder: dict[str, _FakeIngestionLogRepository] = {}

    def build_doc_repo(session: _FakeSession) -> _FakeDocumentRepository:
        repo = _FakeDocumentRepository(session, document)
        doc_repo_holder["repo"] = repo
        return repo

    def build_log_repo(session: _FakeSession) -> _FakeIngestionLogRepository:
        repo = _FakeIngestionLogRepository(session, log)
        log_repo_holder["repo"] = repo
        return repo

    monkeypatch.setattr(db_session, "get_session_factory", lambda: _FakeSessionFactory())
    monkeypatch.setattr(document_repo, "DocumentRepository", build_doc_repo)
    monkeypatch.setattr(ingestion_log_repo, "IngestionLogRepository", build_log_repo)
    return document, log, doc_repo_holder, log_repo_holder


def _install_parse_io(monkeypatch: pytest.MonkeyPatch, router) -> list[tuple[str, str, str]]:
    notifications: list[tuple[str, str, str]] = []
    worker_state.parser_router = router
    monkeypatch.setattr(
        s3_tempfile,
        "stream_s3_object_to_tempfile",
        lambda **kwargs: _FakeTempfile(),
    )
    monkeypatch.setattr(ingest_tasks, "_notify", lambda doc_id, stage, status, error_message=None: notifications.append((stage, status, error_message or "")))
    return notifications


def test_no_text_error_uses_stable_prefix() -> None:
    error = NoTextExtractedError(stage="parse", filename="scan.pdf")

    assert str(error).startswith("NO_TEXT_EXTRACTED")


def test_parse_task_fails_blank_parser_output_before_page_staging(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    document, _log, doc_repo_holder, log_repo_holder = _install_fake_repositories(monkeypatch)
    notifications = _install_parse_io(monkeypatch, _BlankOutcomeRouter())
    page_staging_calls: list[str] = []
    monkeypatch.setattr(
        ingest_tasks,
        "_save_pages_to_s3",
        lambda document_id, pages: page_staging_calls.append(document_id) or "pages-key",
    )

    with pytest.raises(NoTextExtractedError) as exc_info:
        tasks.parse_task.run(
            document_id=str(document.id),
            s3_key="safe/object/key.pdf",
            filename="blank.pdf",
            config_id=str(uuid4()),
        )

    assert str(exc_info.value).startswith("NO_TEXT_EXTRACTED")
    assert page_staging_calls == []
    assert doc_repo_holder["repo"].status_updates[-1] == (document.id, "failed")
    assert log_repo_holder["repo"].stage_updates[-1]["stage"] == "parse"
    assert log_repo_holder["repo"].stage_updates[-1]["status"] == "FAILURE"
    assert notifications[-1][0:2] == ("parse", "FAILURE")


def test_parse_task_maps_low_text_warning_to_no_text_failure(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    document, _log, _doc_repo_holder, log_repo_holder = _install_fake_repositories(monkeypatch)
    _install_parse_io(monkeypatch, _LowTextWarningRouter())

    with pytest.raises(NoTextExtractedError):
        tasks.parse_task.run(
            document_id=str(document.id),
            s3_key="safe/object/key.pdf",
            filename="scan.pdf",
            config_id=str(uuid4()),
        )

    assert log_repo_holder["repo"].stage_updates[-1]["error_message"].startswith(
        "NO_TEXT_EXTRACTED"
    )


def test_chunk_task_fails_zero_usable_chunks_before_embedding(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    document, _log, doc_repo_holder, log_repo_holder = _install_fake_repositories(monkeypatch)
    notifications: list[tuple[str, str, str]] = []
    staged_chunks: list[dict] = []
    deleted_pages: list[str] = []
    deleted_chunks: list[str] = []

    monkeypatch.setattr(ingest_tasks, "_iter_pages_from_s3", lambda document_id: iter(["   ", "\n"]))
    monkeypatch.setattr(
        ingest_tasks,
        "_save_chunks_to_s3",
        lambda document_id, chunks: staged_chunks.extend(list(chunks)) or "chunks-key",
    )
    monkeypatch.setattr(ingest_tasks, "_delete_pages_staging", lambda document_id: deleted_pages.append(document_id))
    monkeypatch.setattr(ingest_tasks, "_delete_staging_file", lambda document_id: deleted_chunks.append(document_id))
    monkeypatch.setattr(ingest_tasks, "_notify", lambda doc_id, stage, status, error_message=None: notifications.append((stage, status, error_message or "")))

    with pytest.raises(NoTextExtractedError):
        tasks.chunk_task.run({"page_count": 2}, document_id=str(document.id), metadata={})

    assert staged_chunks == []
    assert doc_repo_holder["repo"].status_updates[-1] == (document.id, "failed")
    assert log_repo_holder["repo"].stage_updates[-1]["stage"] == "chunk"
    assert log_repo_holder["repo"].stage_updates[-1]["status"] == "FAILURE"
    assert notifications[-2][0:2] == ("chunk", "FAILURE")
    assert notifications[-1][0:2] == ("pipeline", "failed")
    assert deleted_pages == [str(document.id)]
    assert deleted_chunks == [str(document.id)]


def test_embed_task_rejects_zero_chunks_defensively() -> None:
    with pytest.raises(NoTextExtractedError):
        tasks.embed_task.run(
            {"chunk_count": 0},
            document_id=str(uuid4()),
            config_id=str(uuid4()),
        )


@pytest.mark.asyncio
async def test_document_status_exposes_no_text_failure_message() -> None:
    document = _FakeDocument(
        id=uuid4(),
        status="failed",
        metadata_={"playbook_document_id": str(uuid4())},
    )
    log = _FakeIngestionLog(
        parse_status="FAILURE",
        error_message="NO_TEXT_EXTRACTED: No usable text could be extracted.",
    )

    class _DocRepo:
        async def get(self, document_id: UUID) -> _FakeDocument:
            return document

    class _LogRepo:
        async def get_by_document(self, document_id: UUID) -> _FakeIngestionLog:
            return log

    service = IngestionService(_FakeSession())
    service._doc_repo = _DocRepo()
    service._log_repo = _LogRepo()

    response = await service.get_document_status(document.id)

    assert response.status == "failed"
    assert response.error_message == log.error_message
