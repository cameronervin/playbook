from __future__ import annotations

import os
import sys
from collections.abc import Iterator
from types import ModuleType
from typing import Any

import pytest

from app.core.config import Settings
from app.core.log_redaction import REDACTION
from app.observability import langfuse_init


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


@pytest.fixture(autouse=True)
def reset_langfuse_state(monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    env_names = (
        "LANGFUSE_SECRET_KEY",
        "LANGFUSE_PUBLIC_KEY",
        "LANGFUSE_BASE_URL",
    )
    monkeypatch.setattr(langfuse_init, "_initialized", False)
    monkeypatch.setattr(langfuse_init, "_client", None, raising=False)
    for env_name in env_names:
        monkeypatch.delenv(env_name, raising=False)
    yield
    for env_name in env_names:
        os.environ.pop(env_name, None)


def test_init_langfuse_noops_when_disabled(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setitem(sys.modules, "langfuse", ModuleType("langfuse"))

    ready = langfuse_init.init_langfuse(
        _settings(
            LANGFUSE_ENABLED=False,
            LANGFUSE_PUBLIC_KEY="pk-test",
            LANGFUSE_SECRET_KEY="sk-test",
        )
    )

    assert ready is False
    assert langfuse_init.is_langfuse_ready() is False


def test_init_langfuse_requires_credentials() -> None:
    ready = langfuse_init.init_langfuse(
        _settings(
            LANGFUSE_ENABLED=True,
            LANGFUSE_PUBLIC_KEY="",
            LANGFUSE_SECRET_KEY="",
        )
    )

    assert ready is False
    assert langfuse_init.is_langfuse_ready() is False


def test_init_langfuse_creates_client_with_mask(monkeypatch: pytest.MonkeyPatch) -> None:
    created: list[dict[str, Any]] = []

    class FakeLangfuse:
        def __init__(self, **kwargs: Any) -> None:
            created.append(kwargs)

        def shutdown(self) -> None:
            return None

    fake_module = ModuleType("langfuse")
    fake_module.Langfuse = FakeLangfuse
    monkeypatch.setitem(sys.modules, "langfuse", fake_module)

    ready = langfuse_init.init_langfuse(
        _settings(
            LANGFUSE_ENABLED=True,
            LANGFUSE_PUBLIC_KEY="pk-test",
            LANGFUSE_SECRET_KEY="sk-test",
            LANGFUSE_BASE_URL="https://langfuse.test",
        )
    )

    assert ready is True
    assert langfuse_init.is_langfuse_ready() is True
    assert created == [
        {
            "public_key": "pk-test",
            "secret_key": "sk-test",
            "base_url": "https://langfuse.test",
            "environment": "test",
            "mask": langfuse_init.mask_langfuse_data,
        }
    ]


def test_create_langfuse_handler_returns_fresh_callback(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class FakeLangfuse:
        def __init__(self, **_: Any) -> None:
            return None

    class FakeCallbackHandler:
        def __init__(self) -> None:
            return None

    fake_module = ModuleType("langfuse")
    fake_module.Langfuse = FakeLangfuse
    fake_langchain_module = ModuleType("langfuse.langchain")
    fake_langchain_module.CallbackHandler = FakeCallbackHandler
    monkeypatch.setitem(sys.modules, "langfuse", fake_module)
    monkeypatch.setitem(sys.modules, "langfuse.langchain", fake_langchain_module)

    langfuse_init.init_langfuse(
        _settings(
            LANGFUSE_ENABLED=True,
            LANGFUSE_PUBLIC_KEY="pk-test",
            LANGFUSE_SECRET_KEY="sk-test",
        )
    )

    first = langfuse_init.create_langfuse_handler()
    second = langfuse_init.create_langfuse_handler()

    assert isinstance(first, FakeCallbackHandler)
    assert isinstance(second, FakeCallbackHandler)
    assert first is not second


def test_mask_langfuse_data_preserves_trace_content_and_redacts_secrets() -> None:
    payload = {
        "messages": [
            {
                "role": "user",
                "content": "Jane Smith asked from jane.smith@example.edu",
            }
        ],
        "input": "raw prompt with SECRET_TOKEN=super-secret",
        "output": "raw answer with Bearer token-secret",
        "tool_input": "search NIL policy source text",
        "tool_output": "source says submit in Teamworks",
        "source_text": "official policy excerpt",
        "answer": "Submit the NIL disclosure before posting.",
        "metadata": {
            "organization_id": "org-123",
            "assistant_message_id": "msg-456",
            "email": "jane.smith@example.edu",
            "athlete_name": "Jane Smith",
            "athlete_email": "jane.smith@example.edu",
            "provider_subject": "oauth-provider-subject",
            "client_ip": "203.0.113.40",
            "raw_ip_address": "198.51.100.40",
            "source_uri": "s3://private-bucket/org/document.pdf",
            "sourceUri": "s3://private-bucket/org/another-document.pdf",
            "source_text": "private policy source text",
            "storage_key": "org/private/document.pdf",
            "storageKey": "org/private/another-document.pdf",
            "signed_url": "https://storage.test/file.pdf?X-Amz-Signature=abc",
            "public_note": "safe ids only",
        },
    }

    masked = langfuse_init.mask_langfuse_data(payload)
    rendered = repr(masked)

    assert masked["messages"] == [
        {
            "role": "user",
            "content": f"Jane Smith asked from {REDACTION}",
        }
    ]
    assert masked["input"] == f"raw prompt with SECRET_TOKEN={REDACTION}"
    assert masked["output"] == f"raw answer with Bearer {REDACTION}"
    assert masked["tool_input"] == "search NIL policy source text"
    assert masked["tool_output"] == "source says submit in Teamworks"
    assert masked["source_text"] == "official policy excerpt"
    assert masked["answer"] == "Submit the NIL disclosure before posting."
    assert masked["metadata"]["organization_id"] == "org-123"
    assert masked["metadata"]["assistant_message_id"] == "msg-456"
    assert masked["metadata"]["email"] == REDACTION
    assert masked["metadata"]["athlete_name"] == REDACTION
    assert masked["metadata"]["athlete_email"] == REDACTION
    assert masked["metadata"]["provider_subject"] == REDACTION
    assert masked["metadata"]["client_ip"] == REDACTION
    assert masked["metadata"]["raw_ip_address"] == REDACTION
    assert masked["metadata"]["source_uri"] == REDACTION
    assert masked["metadata"]["sourceUri"] == REDACTION
    assert masked["metadata"]["source_text"] == "private policy source text"
    assert masked["metadata"]["storage_key"] == REDACTION
    assert masked["metadata"]["storageKey"] == REDACTION
    assert masked["metadata"]["signed_url"] == REDACTION
    assert masked["metadata"]["public_note"] == "safe ids only"
    assert "jane.smith@example.edu" not in rendered
    assert "oauth-provider-subject" not in rendered
    assert "203.0.113.40" not in rendered
    assert "198.51.100.40" not in rendered
    assert "super-secret" not in rendered
    assert "token-secret" not in rendered
    assert "private-bucket" not in rendered


def test_mask_langfuse_data_redacts_storage_references_inside_trace_text() -> None:
    payload = {
        "prompt": (
            "Review https://storage.test/file.pdf?X-Amz-Signature=abc and "
            "s3://private-bucket/org/document.pdf before answering."
        ),
    }

    masked = langfuse_init.mask_langfuse_data(payload)

    assert masked["prompt"] == (
        f"Review {REDACTION} and {REDACTION} before answering."
    )


def test_shutdown_langfuse_is_idempotent(monkeypatch: pytest.MonkeyPatch) -> None:
    shutdown_calls = 0

    class FakeLangfuse:
        def __init__(self, **_: Any) -> None:
            return None

        def shutdown(self) -> None:
            nonlocal shutdown_calls
            shutdown_calls += 1

    fake_module = ModuleType("langfuse")
    fake_module.Langfuse = FakeLangfuse
    monkeypatch.setitem(sys.modules, "langfuse", fake_module)

    langfuse_init.init_langfuse(
        _settings(
            LANGFUSE_ENABLED=True,
            LANGFUSE_PUBLIC_KEY="pk-test",
            LANGFUSE_SECRET_KEY="sk-test",
        )
    )

    langfuse_init.shutdown_langfuse()
    langfuse_init.shutdown_langfuse()

    assert shutdown_calls == 1
    assert langfuse_init.is_langfuse_ready() is False
