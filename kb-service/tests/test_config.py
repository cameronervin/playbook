"""Tests for KB service settings validation."""

from __future__ import annotations

from pydantic import ValidationError

from app.core.config import Settings


def _base_settings(**overrides: object) -> Settings:
    values = {
        "DATABASE_URL": "postgresql+asyncpg://kb:kb@localhost:5432/kb",
        "KB_WEBHOOK_SECRET": "long-webhook-secret-value-123456",
        "KB_API_SECRET": "long-api-secret-value-1234567890",
        "KB_LLM_PROVIDER_MODE": "direct",
        "OPENAI_API_KEY": "openai-key",
    }
    values.update(overrides)
    return Settings(_env_file=None, **values)


def test_production_rejects_short_shared_secrets() -> None:
    try:
        _base_settings(
            ENVIRONMENT="production",
            KB_API_SECRET="short-api",
            KB_WEBHOOK_SECRET="short-webhook",
        )
    except ValidationError as exc:
        message = str(exc)
    else:
        raise AssertionError("Settings should reject short production secrets")

    assert "KB_API_SECRET must be at least 32 characters" in message
    assert "KB_WEBHOOK_SECRET must be at least 32 characters" in message
