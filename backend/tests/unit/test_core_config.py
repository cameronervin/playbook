"""Tests for Playbook backend settings."""

from pydantic import ValidationError

from app.core.config import Settings


def _base_settings(**overrides: object) -> Settings:
    values = {
        "DATABASE_URL": "postgresql+asyncpg://app:pass@localhost:5432/playbook",
        "SECRET_KEY": "not-the-default-secret",
        "LLM_PROVIDER_MODE": "direct",
        "LLM_DIRECT_PROVIDER": "anthropic",
        "ANTHROPIC_API_KEY": "anthropic-key",
    }
    values.update(overrides)
    return Settings(_env_file=None, **values)


def test_settings_use_playbook_local_defaults() -> None:
    settings = _base_settings()

    assert settings.PROJECT_NAME == "Playbook"
    assert settings.FRONTEND_URL == "http://localhost:3000"
    assert settings.CORS_ORIGINS == ["http://localhost:3000"]
    assert settings.LLM_PROVIDER_MODE == "direct"
    assert settings.LLM_CHAT_MODEL
    assert not hasattr(settings, "LLM_RESEARCH_MODEL")
    assert not hasattr(settings, "RESEARCH_PROVIDER")
    assert not hasattr(settings, "ADVANCED_MODEL")


def test_cors_origins_parse_json_and_comma_separated_values() -> None:
    json_settings = _base_settings(
        CORS_ORIGINS='["http://localhost:3000","http://127.0.0.1:3000"]'
    )
    comma_settings = _base_settings(
        CORS_ORIGINS="http://localhost:3000, http://127.0.0.1:3000"
    )

    assert json_settings.CORS_ORIGINS == [
        "http://localhost:3000",
        "http://127.0.0.1:3000",
    ]
    assert comma_settings.CORS_ORIGINS == [
        "http://localhost:3000",
        "http://127.0.0.1:3000",
    ]


def test_litellm_mode_requires_litellm_connection_settings() -> None:
    try:
        _base_settings(
            LLM_PROVIDER_MODE="litellm",
            LITELLM_BASE_URL="",
            LITELLM_API_KEY="",
        )
    except ValidationError as exc:
        message = str(exc)
    else:
        raise AssertionError("Settings should reject missing LiteLLM config")

    assert "LITELLM_BASE_URL is required" in message
    assert "LITELLM_API_KEY is required" in message


def test_direct_mode_requires_selected_provider_api_key() -> None:
    try:
        _base_settings(
            LLM_PROVIDER_MODE="direct",
            LLM_DIRECT_PROVIDER="openai",
            OPENAI_API_KEY="",
        )
    except ValidationError as exc:
        message = str(exc)
    else:
        raise AssertionError("Settings should reject missing direct provider key")

    assert "OPENAI_API_KEY is required" in message


def test_production_rejects_unsafe_defaults_and_local_urls() -> None:
    try:
        _base_settings(
            ENVIRONMENT="production",
            SECRET_KEY="change-me-in-production",
            FRONTEND_URL="http://localhost:3000",
            CORS_ORIGINS='["*"]',
        )
    except ValidationError as exc:
        message = str(exc)
    else:
        raise AssertionError("Settings should reject unsafe production values")

    assert "SECRET_KEY must be changed" in message
    assert "CORS_ORIGINS cannot contain '*'" in message
    assert "FRONTEND_URL cannot use localhost" in message
