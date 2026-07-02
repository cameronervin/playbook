"""Tests for KB worker Sentry startup lifecycle."""

from __future__ import annotations

import sqlalchemy

from app.infrastructure.chunkers import token_based
from app.infrastructure.parsers.routing import router as parser_router
from app.workers import app as worker_app
from app.workers.state import worker_state


def test_worker_startup_initializes_sentry_once(monkeypatch) -> None:
    calls: list[str] = []

    def fake_init_sentry(
        app_settings,
        *,
        service_name: str,
        include_celery: bool = False,
        include_fastapi: bool = False,
    ) -> bool:
        assert app_settings is worker_app.settings
        assert service_name == "kb-worker"
        assert include_celery is True
        assert include_fastapi is False
        calls.append("init_sentry")
        return True

    monkeypatch.setattr(worker_app, "_worker_loop", None)
    monkeypatch.setattr(worker_app, "_worker_loop_owner_thread", None)
    monkeypatch.setattr(worker_state, "pg_engine", None)
    monkeypatch.setattr(worker_state, "parser_router", None)
    monkeypatch.setattr(worker_state, "text_splitter", None)
    monkeypatch.setattr(worker_state, "_embed_client_factory", None)
    monkeypatch.setattr(worker_app, "init_sentry", fake_init_sentry)
    monkeypatch.setattr(sqlalchemy, "create_engine", lambda *_args, **_kwargs: object())
    monkeypatch.setattr(parser_router, "ParserRouter", lambda: object())
    monkeypatch.setattr(token_based, "_build_text_splitter", lambda: object())

    worker_app.init_worker_resources()
    worker_app.init_worker_resources()

    assert calls == ["init_sentry"]
    assert worker_state.pg_engine is not None
    assert worker_state.parser_router is not None
    assert worker_state.text_splitter is not None

    if worker_app._worker_loop is not None and not worker_app._worker_loop.is_closed():
        worker_app._worker_loop.close()
    monkeypatch.setattr(worker_app, "_worker_loop", None)
    monkeypatch.setattr(worker_app, "_worker_loop_owner_thread", None)
