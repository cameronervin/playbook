from __future__ import annotations

import pytest

from app.core.config import Settings
from app.core.log_redaction import redact_secrets


def test_redact_secrets_masks_nested_secret_values() -> None:
    payload = {
        "LITELLM_API_KEY": "sk-litellm-secret",
        "nested": {
            "KB_WEBHOOK_SECRET": "webhook-secret",
            "items": [{"Authorization": "Bearer token-secret"}],
        },
        "message": "DATABASE_URL=postgresql://user:pass@localhost/db",
    }

    redacted = redact_secrets(payload)
    rendered = repr(redacted)

    assert "sk-litellm-secret" not in rendered
    assert "webhook-secret" not in rendered
    assert "token-secret" not in rendered
    assert "user:pass" not in rendered
    assert "[REDACTED]" in rendered


def test_settings_repr_hides_secret_values() -> None:
    settings = Settings(
        _env_file=None,
        DATABASE_URL="postgresql+asyncpg://user:db-secret@localhost/kb",
        CELERY_BROKER_URL="redis://:broker-secret@localhost:6379/0",
        CELERY_RESULT_BACKEND="redis://:result-secret@localhost:6379/1",
        OPENAI_API_KEY="openai-secret",
        LITELLM_API_KEY="litellm-secret",
        S3_ACCESS_KEY_ID="s3-access-secret",
        S3_SECRET_ACCESS_KEY="s3-secret",
        KB_WEBHOOK_SECRET="webhook-secret-value-that-is-long-enough",
        KB_API_SECRET="kb-secret-value-that-is-long-enough",
    )

    rendered = repr(settings)

    assert "db-secret" not in rendered
    assert "broker-secret" not in rendered
    assert "result-secret" not in rendered
    assert "openai-secret" not in rendered
    assert "litellm-secret" not in rendered
    assert "s3-access-secret" not in rendered
    assert "s3-secret" not in rendered
    assert "webhook-secret-value" not in rendered
    assert "kb-secret-value" not in rendered


def test_settings_validation_errors_hide_secret_inputs() -> None:
    with pytest.raises(ValueError) as exc_info:
        Settings(
            _env_file=None,
            DATABASE_URL={"url": "postgresql+asyncpg://user:db-secret@localhost/kb"},
            KB_WEBHOOK_SECRET="webhook-secret-value-that-is-long-enough",
            KB_API_SECRET="kb-secret-value-that-is-long-enough",
        )

    assert "db-secret" not in str(exc_info.value)
