from __future__ import annotations

from collections.abc import Callable
from typing import Any

from fastapi import FastAPI

from app import main as api_main
from app.core.config import Settings
from app.workers import app as worker_app


def _settings(**overrides: object) -> Settings:
    values: dict[str, object] = {
        "DATABASE_URL": "postgresql+asyncpg://app:pass@localhost:5432/playbook",
        "SECRET_KEY": "test-secret-value-that-is-long-enough",
        "OAUTH_STATE_SECRET": "test-oauth-secret-value-that-is-long-enough",
        "LLM_PROVIDER_MODE": "direct",
        "LLM_DIRECT_PROVIDER": "anthropic",
        "ANTHROPIC_API_KEY": "anthropic-key",
        "TRACING_ENABLED": True,
        "LANGFUSE_ENABLED": True,
        "LANGFUSE_SECRET_KEY": "langfuse-secret",
        "LANGFUSE_PUBLIC_KEY": "langfuse-public",
    }
    values.update(overrides)
    return Settings(_env_file=None, **values)


async def test_fastapi_lifecycle_initializes_and_shutdowns_langfuse(
    monkeypatch,
) -> None:
    settings = _settings()
    app = FastAPI()
    calls: list[str] = []
    checkpointer_pool = object()

    class FakeLLMProvider:
        provider_name = "fake-llm"

        def get_chat_model(self) -> object:
            calls.append("llm")
            return object()

    def fake_init_langfuse(app_settings: Settings) -> None:
        assert app_settings is settings
        calls.append("init_langfuse")

    def fake_verify(app_settings: Settings) -> dict[str, object]:
        assert app_settings is settings
        calls.append("verify_tracing")
        return {"enabled": True, "ready": True}

    async def fake_create_checkpointer_pool(app_settings: Settings) -> object:
        assert app_settings is settings
        calls.append("checkpointer_pool")
        return checkpointer_pool

    async def fake_create_checkpointer(pool: object) -> object:
        assert pool is checkpointer_pool
        calls.append("checkpointer")
        return object()

    async def fake_cleanup_checkpointer_pool(pool: object) -> None:
        assert pool is checkpointer_pool
        calls.append("cleanup_checkpointer")

    monkeypatch.setattr(api_main, "init_langfuse", fake_init_langfuse, raising=False)
    monkeypatch.setattr(api_main, "verify_tracing_configuration", fake_verify)
    monkeypatch.setattr(
        api_main,
        "get_llm_provider",
        lambda *, app_settings: FakeLLMProvider(),
    )
    monkeypatch.setattr(api_main, "is_kb_feature_enabled", lambda _settings: False)
    monkeypatch.setattr(
        api_main,
        "get_storage_provider",
        lambda app_settings: calls.append("storage"),
    )
    monkeypatch.setattr(
        api_main,
        "create_checkpointer_pool",
        fake_create_checkpointer_pool,
    )
    monkeypatch.setattr(api_main, "create_checkpointer", fake_create_checkpointer)
    monkeypatch.setattr(
        api_main,
        "cleanup_checkpointer_pool",
        fake_cleanup_checkpointer_pool,
    )
    monkeypatch.setattr(
        api_main,
        "cleanup_agent_stream_provider",
        _async_call_recorder(calls, "cleanup_stream"),
    )
    monkeypatch.setattr(
        api_main,
        "cleanup_db_engine",
        _async_call_recorder(calls, "cleanup_db"),
    )
    monkeypatch.setattr(
        api_main,
        "cleanup_storage_provider",
        lambda: calls.append("cleanup_storage"),
    )
    monkeypatch.setattr(
        api_main,
        "shutdown_langfuse",
        lambda: calls.append("shutdown_langfuse"),
        raising=False,
    )

    pool, kb_provider = await api_main._init_infrastructure(app, settings)
    await api_main._shutdown_infrastructure(pool, kb_provider)

    assert pool is checkpointer_pool
    assert kb_provider is None
    assert calls[0:2] == ["init_langfuse", "verify_tracing"]
    assert "shutdown_langfuse" in calls


def test_worker_lifecycle_initializes_langfuse_once_and_shutdowns(
    monkeypatch,
) -> None:
    calls: list[str] = []

    def fake_init_langfuse(app_settings: Settings) -> None:
        assert app_settings is worker_app.settings
        calls.append("init_langfuse")

    def fake_verify(app_settings: Settings) -> dict[str, object]:
        assert app_settings is worker_app.settings
        calls.append("verify_tracing")
        return {"enabled": True, "ready": True}

    monkeypatch.setattr(worker_app, "_worker_loop", None)
    monkeypatch.setattr(worker_app, "_worker_loop_owner_thread", None)
    monkeypatch.setattr(worker_app, "_worker_resources_initialized", False)
    monkeypatch.setattr(worker_app, "init_langfuse", fake_init_langfuse, raising=False)
    monkeypatch.setattr(
        worker_app,
        "verify_tracing_configuration",
        fake_verify,
        raising=False,
    )
    monkeypatch.setattr(
        worker_app,
        "cleanup_worker_checkpointer",
        _async_call_recorder(calls, "cleanup_checkpointer"),
    )
    monkeypatch.setattr(
        worker_app,
        "shutdown_langfuse",
        lambda: calls.append("shutdown_langfuse"),
        raising=False,
    )

    worker_app.init_worker_resources()
    worker_app.init_worker_resources()
    worker_app.teardown_worker_resources()

    assert calls.count("init_langfuse") == 1
    assert calls.count("verify_tracing") == 1
    assert calls[-1] == "shutdown_langfuse"


def _async_call_recorder(
    calls: list[str],
    event: str,
) -> Callable[..., Any]:
    async def record(*_: object, **__: object) -> None:
        calls.append(event)

    return record
