"""Tests for KB-service Sentry initialization and privacy scrubbing."""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any

from app.core.config import Settings
from app.core.log_redaction import REDACTION
from app.observability import sentry_init


def _settings(**overrides: object) -> Settings:
    values: dict[str, object] = {
        "DATABASE_URL": "postgresql+asyncpg://kb:kb@localhost:5432/kb",
        "KB_WEBHOOK_SECRET": "long-webhook-secret-value-123456",
        "KB_API_SECRET": "long-api-secret-value-1234567890",
        "LLM_PROVIDER_MODE": "litellm",
        "LITELLM_BASE_URL": "http://litellm:4000",
        "LITELLM_API_KEY": "litellm-key",
    }
    values.update(overrides)
    return Settings(_env_file=None, **values)


def setup_function() -> None:
    sentry_init._reset_sentry_state_for_tests()


def test_init_sentry_stays_disabled_without_dsn(monkeypatch) -> None:
    calls: list[dict[str, Any]] = []
    fake_sdk = SimpleNamespace(
        init=lambda **kwargs: calls.append(kwargs),
        set_tag=lambda *_args, **_kwargs: None,
    )
    monkeypatch.setattr(sentry_init, "_load_sentry_sdk", lambda: fake_sdk)

    ready = sentry_init.init_sentry(
        _settings(SENTRY_ENABLED=True, SENTRY_DSN=""),
        service_name="kb-api",
        include_fastapi=True,
    )

    assert ready is False
    assert calls == []


def test_init_sentry_sets_integrations_and_privacy_options(monkeypatch) -> None:
    calls: list[dict[str, Any]] = []
    tags: list[tuple[str, str]] = []
    fake_sdk = SimpleNamespace(
        init=lambda **kwargs: calls.append(kwargs),
        set_tag=lambda key, value: tags.append((key, value)),
    )
    monkeypatch.setattr(sentry_init, "_load_sentry_sdk", lambda: fake_sdk)
    monkeypatch.setattr(
        sentry_init,
        "_build_integrations",
        lambda *, include_fastapi, include_celery: [
            f"fastapi={include_fastapi}",
            f"celery={include_celery}",
        ],
    )

    ready = sentry_init.init_sentry(
        _settings(
            SENTRY_ENABLED=True,
            SENTRY_DSN="https://public@example.ingest.sentry.io/2",
            SENTRY_ENVIRONMENT="staging",
            SENTRY_RELEASE="kb-service@2026.07.02",
            SENTRY_TRACES_SAMPLE_RATE=0.2,
            SENTRY_PROFILES_SAMPLE_RATE=0.01,
        ),
        service_name="kb-worker",
        include_celery=True,
    )

    assert ready is True
    assert len(calls) == 1
    options = calls[0]
    assert options["environment"] == "staging"
    assert options["release"] == "kb-service@2026.07.02"
    assert options["send_default_pii"] is False
    assert options["max_request_body_size"] == "never"
    assert options["include_local_variables"] is False
    assert options["traces_sample_rate"] == 0.2
    assert options["profiles_sample_rate"] == 0.01
    assert options["integrations"] == ["fastapi=False", "celery=True"]
    assert options["before_send"] is sentry_init.scrub_sentry_event
    assert options["before_send_transaction"] is sentry_init.scrub_sentry_event
    assert ("service", "kb-worker") in tags
    assert ("app", "playbook-kb") in tags


def test_scrub_sentry_event_removes_sensitive_kb_payloads() -> None:
    event = {
        "user": {
            "email": "student@example.edu",
            "ip_address": "203.0.113.10",
        },
        "request": {
            "headers": {
                "Authorization": "Bearer token-secret",
                "Cookie": "session=secret",
                "X-Forwarded-For": "203.0.113.10",
            },
            "query_string": "token=token-secret&safe=1",
            "json": {"source_text": "policy body"},
        },
        "extra": {
            "raw_text": "document contents",
            "summary_input": "summary prompt",
            "source_uri": "s3://bucket/file.pdf?signature=secret",
            "vars": {"openai_api_key": "sk-secret"},
            "remote_addr": "203.0.113.10",
            "collection_id": "collection-123",
        },
    }

    scrubbed = sentry_init.scrub_sentry_event(event)

    assert scrubbed is not None
    rendered = repr(scrubbed)
    assert "student@example.edu" not in rendered
    assert "203.0.113.10" not in rendered
    assert "token-secret" not in rendered
    assert "document contents" not in rendered
    assert "summary prompt" not in rendered
    assert "sk-secret" not in rendered
    assert "user" not in scrubbed
    assert "json" not in scrubbed["request"]
    assert scrubbed["request"]["query_string"] == REDACTION
    assert scrubbed["request"]["headers"]["Authorization"] == REDACTION
    assert scrubbed["request"]["headers"]["Cookie"] == REDACTION
    assert scrubbed["request"]["headers"]["X-Forwarded-For"] == REDACTION
    assert scrubbed["extra"]["collection_id"] == "collection-123"
