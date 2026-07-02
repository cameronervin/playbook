"""Tests for KB service settings validation."""

from __future__ import annotations

from pydantic import ValidationError

from app.core.config import Settings


def _base_settings(**overrides: object) -> Settings:
    values = {
        "DATABASE_URL": "postgresql+asyncpg://kb:kb@localhost:5432/kb",
        "KB_WEBHOOK_SECRET": "long-webhook-secret-value-123456",
        "KB_API_SECRET": "long-api-secret-value-1234567890",
        "LLM_PROVIDER_MODE": "litellm",
        "LITELLM_BASE_URL": "http://litellm:4000",
        "LITELLM_API_KEY": "litellm-key",
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


def test_direct_mode_requires_explicit_openai_key() -> None:
    try:
        _base_settings(LLM_PROVIDER_MODE="direct", OPENAI_API_KEY="")
    except ValidationError as exc:
        message = str(exc)
    else:
        raise AssertionError("Settings should reject missing direct provider key")

    assert "OPENAI_API_KEY is required when LLM_PROVIDER_MODE=direct" in message


def test_production_requires_litellm_unless_break_glass_enabled() -> None:
    try:
        _base_settings(
            ENVIRONMENT="production",
            LLM_PROVIDER_MODE="direct",
            OPENAI_API_KEY="direct-key",
        )
    except ValidationError as exc:
        message = str(exc)
    else:
        raise AssertionError("Settings should reject production direct provider mode")

    assert "LLM_PROVIDER_MODE must be litellm in production" in message

    settings = _base_settings(
        ENVIRONMENT="production",
        LLM_PROVIDER_MODE="direct",
        OPENAI_API_KEY="direct-key",
        ALLOW_DIRECT_LLM_IN_PROD=True,
    )

    assert settings.ALLOW_DIRECT_LLM_IN_PROD is True


def test_ocr_provider_defaults_to_none() -> None:
    settings = _base_settings()

    assert settings.OCR_PROVIDER == "none"
    assert settings.SENTRY_ENABLED is False
    assert settings.SENTRY_DSN == ""
    assert settings.SENTRY_ENVIRONMENT == ""
    assert settings.SENTRY_RELEASE == ""
    assert settings.SENTRY_TRACES_SAMPLE_RATE == 0.1
    assert settings.SENTRY_PROFILES_SAMPLE_RATE == 0.0


def test_sentry_runtime_settings_accept_env_overrides() -> None:
    settings = _base_settings(
        SENTRY_ENABLED=True,
        SENTRY_DSN="https://public@example.ingest.sentry.io/2",
        SENTRY_ENVIRONMENT="staging",
        SENTRY_RELEASE="kb-service@2026.07.02",
        SENTRY_TRACES_SAMPLE_RATE="0.2",
        SENTRY_PROFILES_SAMPLE_RATE="0.01",
    )

    assert settings.SENTRY_ENABLED is True
    assert settings.SENTRY_DSN.startswith("https://public@")
    assert settings.SENTRY_ENVIRONMENT == "staging"
    assert settings.SENTRY_RELEASE == "kb-service@2026.07.02"
    assert settings.SENTRY_TRACES_SAMPLE_RATE == 0.2
    assert settings.SENTRY_PROFILES_SAMPLE_RATE == 0.01


def test_rerank_placeholders_default_to_disabled_litellm_alias() -> None:
    settings = _base_settings()

    assert settings.LITELLM_RERANK_MODEL == "playbook-rerank"
    assert settings.KB_RERANK_ENABLED is False
    assert settings.KB_RERANK_CANDIDATE_LIMIT == 50
    assert settings.KB_RERANK_TIMEOUT_SECONDS == 10.0
    assert settings.KB_RERANK_FAIL_OPEN is True


def test_hybrid_search_defaults_to_semantic_only() -> None:
    settings = _base_settings()

    assert settings.KB_SEARCH_STRATEGY == "semantic"
    assert settings.KB_HYBRID_CANDIDATE_LIMIT == 50
    assert settings.KB_RRF_K == 60


def test_hybrid_search_settings_accept_env_overrides() -> None:
    settings = _base_settings(
        KB_SEARCH_STRATEGY="hybrid",
        KB_HYBRID_CANDIDATE_LIMIT="25",
        KB_RRF_K="42",
    )

    assert settings.KB_SEARCH_STRATEGY == "hybrid"
    assert settings.KB_HYBRID_CANDIDATE_LIMIT == 25
    assert settings.KB_RRF_K == 42


def test_rerank_placeholders_accept_env_overrides() -> None:
    settings = _base_settings(
        LITELLM_RERANK_MODEL="custom-rerank",
        KB_RERANK_ENABLED="true",
        KB_RERANK_CANDIDATE_LIMIT="25",
        KB_RERANK_TIMEOUT_SECONDS="2.5",
        KB_RERANK_FAIL_OPEN="false",
    )

    assert settings.LITELLM_RERANK_MODEL == "custom-rerank"
    assert settings.KB_RERANK_ENABLED is True
    assert settings.KB_RERANK_CANDIDATE_LIMIT == 25
    assert settings.KB_RERANK_TIMEOUT_SECONDS == 2.5
    assert settings.KB_RERANK_FAIL_OPEN is False


def test_enabled_rerank_requires_litellm_connection_settings() -> None:
    try:
        _base_settings(
            LLM_PROVIDER_MODE="direct",
            OPENAI_API_KEY="direct-key",
            KB_RERANK_ENABLED=True,
            LITELLM_BASE_URL="",
            LITELLM_API_KEY="",
            LITELLM_RERANK_MODEL="",
        )
    except ValidationError as exc:
        message = str(exc)
    else:
        raise AssertionError("Settings should reject missing LiteLLM rerank config")

    assert "LITELLM_BASE_URL is required when KB_RERANK_ENABLED=true" in message
    assert "LITELLM_API_KEY is required when KB_RERANK_ENABLED=true" in message
    assert "LITELLM_RERANK_MODEL is required when KB_RERANK_ENABLED=true" in message


def test_vlm_ocr_requires_litellm_connection_settings() -> None:
    try:
        _base_settings(
            LLM_PROVIDER_MODE="direct",
            OPENAI_API_KEY="direct-key",
            OCR_PROVIDER="vlm",
            LITELLM_BASE_URL="",
            LITELLM_API_KEY="",
            LITELLM_VLM_MODEL="",
        )
    except ValidationError as exc:
        message = str(exc)
    else:
        raise AssertionError("Settings should reject missing VLM LiteLLM config")

    assert "LITELLM_BASE_URL is required when OCR_PROVIDER=vlm" in message
    assert "LITELLM_API_KEY is required when OCR_PROVIDER=vlm" in message
    assert "LITELLM_VLM_MODEL is required when OCR_PROVIDER=vlm" in message


def test_vlm_ocr_allows_direct_embedding_mode_with_litellm_vision() -> None:
    settings = _base_settings(
        LLM_PROVIDER_MODE="direct",
        OPENAI_API_KEY="direct-key",
        OCR_PROVIDER="vlm",
        LITELLM_BASE_URL="http://litellm:4000",
        LITELLM_API_KEY="litellm-key",
        LITELLM_VLM_MODEL="playbook-ocr",
    )

    assert settings.OCR_PROVIDER == "vlm"
    assert settings.LITELLM_VLM_MODEL == "playbook-ocr"


def test_canonical_s3_settings_populate_runtime_config() -> None:
    settings = _base_settings(
        S3_BUCKET_NAME="playbook-bucket",
        S3_ENDPOINT_URL="http://localhost:9000",
        S3_REGION="us-west-2",
        S3_ACCESS_KEY_ID="minio-user",
        S3_SECRET_ACCESS_KEY="minio-secret",
    )

    assert settings.S3_BUCKET_NAME == "playbook-bucket"
    assert settings.S3_ENDPOINT_URL == "http://localhost:9000"
    assert settings.S3_REGION == "us-west-2"
    assert settings.S3_ACCESS_KEY_ID == "minio-user"
    assert settings.S3_SECRET_ACCESS_KEY == "minio-secret"


def test_legacy_gateway_mode_no_longer_satisfies_provider_mode() -> None:
    try:
        _base_settings(
            LLM_PROVIDER_MODE="gateway",
            LITELLM_BASE_URL="",
            LITELLM_API_KEY="",
            LLM_GATEWAY_BASE_URL="http://litellm:4000",
            LLM_GATEWAY_API_KEY="legacy-key",
        )
    except ValidationError as exc:
        message = str(exc)
    else:
        raise AssertionError("Settings should reject legacy gateway mode")

    assert "Input should be 'direct' or 'litellm'" in message


def test_legacy_env_names_do_not_satisfy_litellm_or_s3_settings() -> None:
    try:
        settings = _base_settings(
            LITELLM_BASE_URL="",
            LITELLM_API_KEY="",
            LLM_GATEWAY_BASE_URL="http://litellm:4000",
            LLM_GATEWAY_API_KEY="legacy-key",
            AWS_S3_BUCKET="legacy-bucket",
            AWS_S3_ENDPOINT_URL="http://legacy-minio:9000",
            AWS_REGION="us-west-1",
            AWS_ACCESS_KEY_ID="legacy-user",
            AWS_SECRET_ACCESS_KEY="legacy-secret",
        )
    except ValidationError as exc:
        message = str(exc)
    else:
        raise AssertionError(
            "Legacy LiteLLM names should not satisfy litellm validation"
        )

    assert "LITELLM_BASE_URL is required" in message
    assert "LITELLM_API_KEY is required" in message

    settings = _base_settings(
        AWS_S3_BUCKET="legacy-bucket",
        AWS_S3_ENDPOINT_URL="http://legacy-minio:9000",
        AWS_REGION="us-west-1",
        AWS_ACCESS_KEY_ID="legacy-user",
        AWS_SECRET_ACCESS_KEY="legacy-secret",
    )
    assert settings.S3_BUCKET_NAME == "playbook-bucket"
    assert settings.S3_ENDPOINT_URL == ""
    assert settings.S3_REGION == "us-east-1"
    assert settings.S3_ACCESS_KEY_ID == ""
    assert settings.S3_SECRET_ACCESS_KEY == ""
