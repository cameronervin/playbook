"""Tests for backend Sentry initialization and privacy scrubbing."""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any

from app.core.config import Settings
from app.core.log_redaction import REDACTION
from app.observability import sentry_init


def _settings(**overrides: object) -> Settings:
    values: dict[str, object] = {
        "DATABASE_URL": "postgresql+asyncpg://app:pass@localhost:5432/playbook",
        "SECRET_KEY": "test-secret-value-that-is-long-enough",
        "OAUTH_STATE_SECRET": "test-oauth-secret-value-that-is-long-enough",
        "LLM_PROVIDER_MODE": "direct",
        "LLM_DIRECT_PROVIDER": "anthropic",
        "ANTHROPIC_API_KEY": "anthropic-key",
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
        service_name="backend-api",
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
            SENTRY_DSN="https://public@example.ingest.sentry.io/1",
            SENTRY_ENVIRONMENT="staging",
            SENTRY_RELEASE="playbook@2026.07.02",
            SENTRY_TRACES_SAMPLE_RATE=0.25,
            SENTRY_PROFILES_SAMPLE_RATE=0.05,
        ),
        service_name="backend-api",
        include_fastapi=True,
    )

    assert ready is True
    assert len(calls) == 1
    options = calls[0]
    assert options["environment"] == "staging"
    assert options["release"] == "playbook@2026.07.02"
    assert options["send_default_pii"] is False
    assert options["max_request_body_size"] == "never"
    assert options["include_local_variables"] is False
    assert options["traces_sample_rate"] == 0.25
    assert options["profiles_sample_rate"] == 0.05
    assert options["integrations"] == ["fastapi=True", "celery=False"]
    assert options["before_send"] is sentry_init.scrub_sentry_event
    assert options["before_send_transaction"] is sentry_init.scrub_sentry_event
    assert ("service", "backend-api") in tags
    assert ("app", "playbook") in tags


def test_scrub_sentry_event_removes_sensitive_payloads() -> None:
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
                "X-Request-ID": "req-1",
            },
            "query_string": "token=token-secret&safe=1",
            "data": {"prompt": "where is the NIL policy?"},
            "cookies": {"session": "secret"},
        },
        "extra": {
            "prompt": "student prompt",
            "source_text": "policy source text",
            "source_uri": "https://bucket/file.pdf?X-Amz-Signature=secret",
            "presigned_url": "https://bucket/file.pdf?token=secret",
            "vars": {"api_key": "sk-secret"},
            "client_ip": "203.0.113.10",
            "safe_id": "org-123",
        },
    }

    scrubbed = sentry_init.scrub_sentry_event(event)

    assert scrubbed is not None
    rendered = repr(scrubbed)
    assert "student@example.edu" not in rendered
    assert "203.0.113.10" not in rendered
    assert "token-secret" not in rendered
    assert "student prompt" not in rendered
    assert "policy source text" not in rendered
    assert "sk-secret" not in rendered
    assert "user" not in scrubbed
    assert "data" not in scrubbed["request"]
    assert "cookies" not in scrubbed["request"]
    assert scrubbed["request"]["query_string"] == REDACTION
    assert scrubbed["request"]["headers"]["Authorization"] == REDACTION
    assert scrubbed["request"]["headers"]["Cookie"] == REDACTION
    assert scrubbed["request"]["headers"]["X-Forwarded-For"] == REDACTION
    assert scrubbed["extra"]["safe_id"] == "org-123"


def test_capture_exception_is_noop_until_initialized(monkeypatch) -> None:
    captured: list[BaseException] = []
    fake_sdk = SimpleNamespace(capture_exception=lambda exc: captured.append(exc))
    monkeypatch.setattr(sentry_init, "_load_sentry_sdk", lambda: fake_sdk)

    sentry_init.capture_exception(RuntimeError("not-ready"))

    assert captured == []
