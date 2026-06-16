from __future__ import annotations

import pytest

from app.core.config import Settings
from app.core.log_redaction import redact_secrets


def test_redact_secrets_masks_nested_secret_values() -> None:
    payload = {
        "OPENAI_API_KEY": "sk-openai-secret",
        "source_uri": "https://storage.test/file.pdf?signature=source-secret",
        "model_input": "private prompt with file text",
        "nested": {
            "KB_API_SECRET": "kb-secret",
            "headers": {"Authorization": "Bearer token-secret"},
            "raw_text": "full private extracted text",
            "file_contents": "binary-ish private file contents",
        },
        "message": "DATABASE_URL=postgresql://user:pass@localhost/db",
    }

    redacted = redact_secrets(payload)
    rendered = repr(redacted)

    assert "sk-openai-secret" not in rendered
    assert "kb-secret" not in rendered
    assert "source-secret" not in rendered
    assert "private prompt" not in rendered
    assert "full private extracted text" not in rendered
    assert "binary-ish private file contents" not in rendered
    assert "token-secret" not in rendered
    assert "user:pass" not in rendered
    assert "[REDACTED]" in rendered


def test_settings_repr_hides_secret_values() -> None:
    settings = Settings(
        _env_file=None,
        DATABASE_URL="postgresql+asyncpg://user:db-secret@localhost/playbook",
        LANGGRAPH_CHECKPOINT_DB_URL="postgresql+asyncpg://user:checkpoint-secret@localhost/playbook",
        SECRET_KEY="settings-secret-value-that-is-long-enough",
        OAUTH_STATE_SECRET="oauth-secret-value-that-is-long-enough",
        LITELLM_API_KEY="litellm-secret",
        ANTHROPIC_API_KEY="anthropic-secret",
        OPENAI_API_KEY="openai-secret",
        GEMINI_API_KEY="gemini-secret",
        S3_ACCESS_KEY_ID="s3-access-secret",
        S3_SECRET_ACCESS_KEY="s3-secret",
        KB_API_SECRET="kb-api-secret",
        KB_WEBHOOK_SECRET="kb-webhook-secret",
        LANGFUSE_SECRET_KEY="langfuse-secret",
    )

    rendered = repr(settings)

    assert "db-secret" not in rendered
    assert "checkpoint-secret" not in rendered
    assert "settings-secret-value" not in rendered
    assert "oauth-secret-value" not in rendered
    assert "litellm-secret" not in rendered
    assert "anthropic-secret" not in rendered
    assert "openai-secret" not in rendered
    assert "gemini-secret" not in rendered
    assert "s3-access-secret" not in rendered
    assert "s3-secret" not in rendered
    assert "kb-api-secret" not in rendered
    assert "kb-webhook-secret" not in rendered
    assert "langfuse-secret" not in rendered


def test_settings_validation_errors_hide_secret_inputs() -> None:
    with pytest.raises(ValueError) as exc_info:
        Settings(
            _env_file=None,
            DATABASE_URL={"url": "postgresql+asyncpg://user:db-secret@localhost/playbook"},
            SECRET_KEY="settings-secret-value-that-is-long-enough",
            OAUTH_STATE_SECRET="oauth-secret-value-that-is-long-enough",
            ANTHROPIC_API_KEY="anthropic-secret",
        )

    assert "db-secret" not in str(exc_info.value)
