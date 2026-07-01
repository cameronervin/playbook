from __future__ import annotations

from uuid import uuid4

from app.core.config import Settings
from app.observability import agent_trace


def _settings(**overrides: object) -> Settings:
    values: dict[str, object] = {
        "DATABASE_URL": "postgresql+asyncpg://app:pass@localhost:5432/playbook",
        "SECRET_KEY": "test-secret-value-that-is-long-enough",
        "LLM_PROVIDER_MODE": "direct",
        "LLM_DIRECT_PROVIDER": "anthropic",
        "ANTHROPIC_API_KEY": "anthropic-key",
        "ENVIRONMENT": "test",
    }
    values.update(overrides)
    return Settings(_env_file=None, **values)


def test_verify_tracing_configuration_reports_disabled_when_tracing_off(
    monkeypatch,
) -> None:
    monkeypatch.setattr(agent_trace, "is_langfuse_ready", lambda: True)

    status = agent_trace.verify_tracing_configuration(
        _settings(TRACING_ENABLED=False, LANGFUSE_ENABLED=True)
    )

    assert status == {
        "enabled": False,
        "provider": "langfuse",
        "ready": False,
    }


def test_verify_tracing_configuration_reports_missing_langfuse_readiness(
    monkeypatch,
) -> None:
    monkeypatch.setattr(agent_trace, "is_langfuse_ready", lambda: False)

    status = agent_trace.verify_tracing_configuration(
        _settings(TRACING_ENABLED=True, LANGFUSE_ENABLED=True)
    )

    assert status == {
        "enabled": True,
        "provider": "langfuse",
        "ready": False,
    }


def test_build_graph_invoke_config_omits_callbacks_when_tracing_disabled(
    monkeypatch,
) -> None:
    monkeypatch.setattr(agent_trace, "is_langfuse_ready", lambda: True)
    monkeypatch.setattr(agent_trace, "create_langfuse_handler", object)

    config = agent_trace.build_graph_invoke_config(
        thread_id=uuid4(),
        phase="respond",
        mode="athlete_chat",
        settings=_settings(TRACING_ENABLED=False, LANGFUSE_ENABLED=True),
    )

    assert "callbacks" not in config


def test_build_graph_invoke_config_omits_callbacks_without_ready_langfuse(
    monkeypatch,
) -> None:
    monkeypatch.setattr(agent_trace, "is_langfuse_ready", lambda: False)
    monkeypatch.setattr(agent_trace, "create_langfuse_handler", object)

    config = agent_trace.build_graph_invoke_config(
        thread_id=uuid4(),
        phase="respond",
        mode="athlete_chat",
        settings=_settings(TRACING_ENABLED=True, LANGFUSE_ENABLED=True),
    )

    assert "callbacks" not in config


def test_build_graph_invoke_config_attaches_fresh_langfuse_callback(
    monkeypatch,
) -> None:
    created: list[object] = []

    def fake_create_handler() -> object:
        handler = object()
        created.append(handler)
        return handler

    monkeypatch.setattr(agent_trace, "is_langfuse_ready", lambda: True)
    monkeypatch.setattr(agent_trace, "create_langfuse_handler", fake_create_handler)
    settings = _settings(TRACING_ENABLED=True, LANGFUSE_ENABLED=True)

    first = agent_trace.build_graph_invoke_config(
        thread_id=uuid4(),
        phase="respond",
        mode="athlete_chat",
        settings=settings,
    )
    second = agent_trace.build_graph_invoke_config(
        thread_id=uuid4(),
        phase="respond",
        mode="athlete_chat",
        settings=settings,
    )

    assert first["callbacks"] == [created[0]]
    assert second["callbacks"] == [created[1]]
    assert first["callbacks"][0] is not second["callbacks"][0]


def test_build_graph_invoke_config_attaches_safe_trace_metadata_only(
    monkeypatch,
) -> None:
    handler = object()
    thread_id = uuid4()
    organization_id = uuid4()
    user_message_id = uuid4()
    assistant_message_id = uuid4()

    monkeypatch.setattr(agent_trace, "is_langfuse_ready", lambda: True)
    monkeypatch.setattr(agent_trace, "create_langfuse_handler", lambda: handler)

    config = agent_trace.build_graph_invoke_config(
        thread_id=thread_id,
        phase="respond",
        mode="athlete_chat",
        settings=_settings(TRACING_ENABLED=True, LANGFUSE_ENABLED=True),
        extra_configurable={
            "task_id": "task-123",
            "organization_id": str(organization_id),
            "user_message_id": str(user_message_id),
            "assistant_message_id": str(assistant_message_id),
            "attached_file_ids": [str(uuid4())],
            "raw_query": "What is jane.smith@example.edu allowed to earn?",
            "source_uri": "s3://private-bucket/org/document.pdf",
        },
    )

    assert config["callbacks"] == [handler]
    assert config["metadata"] == {
        "environment": "test",
        "mode": "athlete_chat",
        "phase": "respond",
        "task_id": "task-123",
        "organization_id": str(organization_id),
        "conversation_id": str(thread_id),
        "user_message_id": str(user_message_id),
        "assistant_message_id": str(assistant_message_id),
    }
    assert config["tags"] == [
        "playbook",
        "env:test",
        "mode:athlete_chat",
        "phase:respond",
    ]
    assert "raw_query" not in config["metadata"]
    assert "source_uri" not in config["metadata"]
    assert "attached_file_ids" not in config["metadata"]
