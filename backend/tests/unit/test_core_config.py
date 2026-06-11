"""Tests for Playbook backend settings."""

import os
from pathlib import Path
import subprocess
import sys

from pydantic import ValidationError

from app.core.config import Settings

BACKEND_ROOT = Path(__file__).resolve().parents[2]


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


def _conflicting_env() -> dict[str, str]:
    env = os.environ.copy()
    env.update(
        {
            "ENVIRONMENT": "local",
            "DEBUG": "release",
            "DEV_AUTH_ENABLED": "true",
            "ANTHROPIC_API_KEY": "test",
        }
    )
    return env


def test_importing_config_module_does_not_validate_runtime_environment() -> None:
    result = subprocess.run(
        [
            sys.executable,
            "-c",
            "import app.core.config; print('import-ok')",
        ],
        cwd=BACKEND_ROOT,
        env=_conflicting_env(),
        text=True,
        capture_output=True,
        check=False,
    )

    assert result.returncode == 0
    assert "import-ok" in result.stdout


def test_get_settings_preserves_runtime_validation() -> None:
    result = subprocess.run(
        [
            sys.executable,
            "-c",
            "from app.core.config import get_settings; get_settings()",
        ],
        cwd=BACKEND_ROOT,
        env=_conflicting_env(),
        text=True,
        capture_output=True,
        check=False,
    )

    assert result.returncode != 0
    assert "DEV_AUTH_ENABLED can only be true" in result.stderr


def test_settings_use_playbook_local_defaults() -> None:
    settings = _base_settings()

    assert settings.PROJECT_NAME == "Playbook"
    assert settings.DEV_AUTH_ENABLED is False
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


def test_production_rejects_short_security_secrets() -> None:
    try:
        _base_settings(
            ENVIRONMENT="production",
            SECRET_KEY="short-secret",
            OAUTH_STATE_SECRET="short-oauth-secret",
            KB_PROVIDER_MODE="local",
            KB_API_SECRET="short-kb-api",
            KB_WEBHOOK_SECRET="short-webhook",
            FRONTEND_URL="https://app.example.com",
            API_PUBLIC_URL="https://api.example.com",
            CORS_ORIGINS='["https://app.example.com"]',
        )
    except ValidationError as exc:
        message = str(exc)
    else:
        raise AssertionError("Settings should reject short production secrets")

    assert "SECRET_KEY must be at least 32 characters" in message
    assert "OAUTH_STATE_SECRET must be at least 32 characters" in message
    assert "KB_API_SECRET must be at least 32 characters" in message
    assert "KB_WEBHOOK_SECRET must be at least 32 characters" in message


def test_dev_auth_can_only_be_enabled_for_local_debug() -> None:
    local_settings = _base_settings(ENVIRONMENT="local", DEBUG=True, DEV_AUTH_ENABLED=True)
    development_settings = _base_settings(
        ENVIRONMENT="development",
        DEBUG=True,
        DEV_AUTH_ENABLED=True,
    )

    assert local_settings.DEV_AUTH_ENABLED is True
    assert development_settings.DEV_AUTH_ENABLED is True

    for environment, debug in (("local", False), ("dev", True), ("production", True)):
        try:
            _base_settings(
                ENVIRONMENT=environment,
                DEBUG=debug,
                DEV_AUTH_ENABLED=True,
                FRONTEND_URL="https://app.example.com",
                API_PUBLIC_URL="https://api.example.com",
                CORS_ORIGINS='["https://app.example.com"]',
                OAUTH_STATE_SECRET="not-the-default-oauth-secret-value",
                KB_API_SECRET="not-the-default-kb-api-secret-value",
                KB_WEBHOOK_SECRET="not-the-default-kb-webhook-secret-value",
            )
        except ValidationError as exc:
            message = str(exc)
        else:
            raise AssertionError("Settings should reject unsafe dev auth enablement")

        assert "DEV_AUTH_ENABLED can only be true in local/development debug mode" in message
