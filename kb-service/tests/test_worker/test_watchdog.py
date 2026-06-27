from __future__ import annotations

from types import SimpleNamespace
from uuid import uuid4

import pytest

import app.infrastructure.db.session as db_session
from app.workers.tasks import watchdog
from app.workers.tasks import finalize


class _FakeResult:
    def __init__(self, rows: list[tuple[object, object]]) -> None:
        self._rows = rows

    def fetchall(self) -> list[tuple[object, object]]:
        return self._rows


class _FakeSession:
    def __init__(self, rows: list[tuple[object, object]]) -> None:
        self.rows = rows
        self.params: dict[str, object] | None = None

    async def __aenter__(self) -> "_FakeSession":
        return self

    async def __aexit__(self, exc_type, exc, tb) -> None:
        return None

    async def execute(self, statement, params: dict[str, object]) -> _FakeResult:
        self.params = params
        return _FakeResult(self.rows)


class _FakeSessionFactory:
    def __init__(self, session: _FakeSession) -> None:
        self.session = session

    def __call__(self) -> _FakeSession:
        return self.session


def test_reconcile_stuck_embeds_dispatches_load_vector_for_stale_rows(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    document_id = uuid4()
    config_id = uuid4()
    session = _FakeSession(rows=[(document_id, config_id)])
    dispatched: list[dict[str, object]] = []

    monkeypatch.setattr(
        db_session,
        "get_session_factory",
        lambda: _FakeSessionFactory(session),
    )
    monkeypatch.setattr(
        finalize.load_vector_task,
        "apply_async",
        lambda *, kwargs: dispatched.append(kwargs) or SimpleNamespace(id="load-task"),
    )

    summary = watchdog.reconcile_stuck_embeds.run(stuck_minutes=9)

    assert session.params == {"mins": 9}
    assert dispatched == [
        {"document_id": str(document_id), "config_id": str(config_id)}
    ]
    assert summary == {
        "scanned": 1,
        "dispatched": 1,
        "doc_ids": [str(document_id)],
        "stuck_minutes": 9,
    }


def test_reconcile_stuck_embeds_returns_empty_summary_without_stale_rows(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    session = _FakeSession(rows=[])

    def fail_dispatch(*args, **kwargs):
        raise AssertionError("load_vector_task should not dispatch without rows")

    monkeypatch.setattr(
        db_session,
        "get_session_factory",
        lambda: _FakeSessionFactory(session),
    )
    monkeypatch.setattr(finalize.load_vector_task, "apply_async", fail_dispatch)

    summary = watchdog.reconcile_stuck_embeds.run(stuck_minutes=5)

    assert summary == {
        "scanned": 0,
        "dispatched": 0,
        "doc_ids": [],
        "stuck_minutes": 5,
    }
