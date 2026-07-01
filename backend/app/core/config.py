"""Application settings for the Playbook backend."""

from __future__ import annotations

import json
from functools import lru_cache
from typing import Annotated, Any, Literal

from fastapi import Request
from pydantic import Field, field_validator, model_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict


def _is_local_url(value: str) -> bool:
    return "localhost" in value or "127.0.0.1" in value


def _is_production_environment(value: str) -> bool:
    return value.lower() in {"prod", "production"}


def _require_min_secret_length(
    errors: list[str],
    *,
    name: str,
    value: str,
    minimum: int = 32,
) -> None:
    if len(value) < minimum:
        errors.append(f"{name} must be at least {minimum} characters")


class Settings(BaseSettings):
    # --- Application -----------------------------------------------------------
    PROJECT_NAME: str = "Playbook"
    ENVIRONMENT: str = "local"
    DEBUG: bool = True
    LOG_LEVEL: str = "DEBUG"

    # --- Database --------------------------------------------------------------
    DATABASE_URL: str = Field(
        default="postgresql+asyncpg://app:localpass@localhost:5433/playbook",
        repr=False,
    )

    # LangGraph checkpoint database (optional — defaults to DATABASE_URL)
    LANGGRAPH_CHECKPOINT_DB_URL: str | None = Field(default=None, repr=False)

    # --- Security --------------------------------------------------------------
    SECRET_KEY: str = Field(default="change-me-in-production", repr=False)
    CORS_ORIGINS: Annotated[list[str], NoDecode] = ["http://localhost:3000"]
    FRONTEND_URL: str = "http://localhost:3000"
    API_PUBLIC_URL: str = "http://localhost:8000"

    JWT_LIFETIME_SECONDS: int = 3600  # 1 hour
    JWT_REFRESH_THRESHOLD_SECONDS: int = 1800  # Renew if < 30 min remaining
    # Cookie domain: "" or "localhost" for local dev, ".example.com" for prod
    COOKIE_DOMAIN: str = "localhost"
    OAUTH_STATE_SECRET: str = Field(default="change-me-oauth-state", repr=False)
    OAUTH_STATE_COOKIE_NAME: str = "playbook_oauth_state"
    ACCESS_TOKEN_COOKIE_NAME: str = "access_token"
    DEV_AUTH_ENABLED: bool = False

    GOOGLE_OAUTH_CLIENT_ID: str = ""
    GOOGLE_OAUTH_CLIENT_SECRET: str = Field(default="", repr=False)
    MICROSOFT_OAUTH_CLIENT_ID: str = ""
    MICROSOFT_OAUTH_CLIENT_SECRET: str = Field(default="", repr=False)
    MICROSOFT_OAUTH_TENANT: str = "common"

    DEFAULT_ORGANIZATION_NAME: str = "Playbook Athletics"
    DEFAULT_ORGANIZATION_SLUG: str = "playbook"

    # --- AWS / S3-compatible storage -------------------------------------------
    # Set S3_ENDPOINT_URL to a MinIO URL (e.g. http://minio:9000) for local/dev.
    # Leave empty/None for production AWS S3.
    S3_ENDPOINT_URL: str | None = None
    # Optional browser-facing S3-compatible endpoint for direct upload contracts.
    # Local Docker uses S3_ENDPOINT_URL=http://minio:9000 internally while the
    # browser must POST to http://localhost:9000.
    S3_PUBLIC_ENDPOINT_URL: str | None = None
    S3_BUCKET_NAME: str = "playbook-bucket"
    S3_REGION: str = "us-east-1"
    # Explicit credentials (MinIO: local dev credentials). If unset, boto3
    # falls back to AWS_PROFILE, then the default credential chain / IAM role
    S3_ACCESS_KEY_ID: str | None = Field(default=None, repr=False)
    S3_SECRET_ACCESS_KEY: str | None = Field(default=None, repr=False)
    AWS_PROFILE: str | None = None
    S3_TIMEOUT: int = 120
    S3_PRESIGNED_URL_EXPIRY: int = 3600
    CONVERSATION_FILE_MAX_UPLOAD_MB: int = 200

    # --- Workers ---------------------------------------------------------------
    CELERY_BROKER_URL: str = Field(default="redis://localhost:6379/0", repr=False)
    CELERY_RESULT_BACKEND: str = Field(default="redis://localhost:6379/1", repr=False)
    CELERY_TASK_SOFT_TIME_LIMIT: int = 600  # 10 min
    CELERY_TASK_HARD_TIME_LIMIT: int = 660
    CELERY_TASK_MAX_RETRIES: int = 3
    CELERY_TASK_RETRY_COUNTDOWN: int = 60  # seconds before retry
    CELERY_WORKER_LOG_LEVEL: str = "INFO"
    AGENT_STREAM_VALKEY_URL: str = Field(default="redis://localhost:6379/2", repr=False)

    # --- LLM --------------------------------------------------------------------
    # "litellm" = route every request through a LiteLLM OpenAI-compatible proxy
    # "direct" = call the selected model provider SDK directly
    LLM_PROVIDER_MODE: Literal["direct", "litellm"] = "direct"
    LLM_CHAT_MODEL: str = "claude-sonnet-4-6"
    LLM_TITLE_MODEL: str = ""
    LLM_DIRECT_PROVIDER: Literal["anthropic", "openai", "google"] = "anthropic"

    # --- LiteLLM mode ---
    LITELLM_BASE_URL: str = "http://localhost:4000"
    LITELLM_API_KEY: str = Field(default="", repr=False)

    # --- Common LLM settings (all modes) ---
    LLM_TEMPERATURE: float = 0.2
    LLM_MAX_TOKENS: int = 16384
    LLM_TIMEOUT: int = 600

    # --- API keys (required based on provider selection) ---
    ANTHROPIC_API_KEY: str | None = Field(default=None, repr=False)
    OPENAI_API_KEY: str | None = Field(default=None, repr=False)
    GEMINI_API_KEY: str | None = Field(default=None, repr=False)

    # --- Eval harness (dev/CI only — see backend/evals) ---
    # Judge LLM for the eval harness; falls back to LLM_CHAT_MODEL when empty
    EVAL_JUDGE_MODEL: str = ""
    # Embeddings model for Ragas answer_relevancy (routed through LiteLLM)
    EVAL_EMBEDDINGS_MODEL: str = "text-embedding-3-small"

    # --- Knowledgebase ---------------------------------------------------------
    # Provider mode: local | mock (see knowledgebase.factory.KBProviderMode)
    KB_PROVIDER_MODE: str = "mock"
    # Feature flag — set false to detach KB tools entirely
    KB_ENABLED: bool = True

    # Local KB service connection (only used when KB_PROVIDER_MODE=local)
    KB_LOCAL_BASE_URL: str = "http://kb-api:8001"
    KB_API_SECRET: str = Field(default="", repr=False)  # Bearer token sent with every call to the KB service
    KB_WEBHOOK_SECRET: str = Field(default="", repr=False)
    KB_CONFIG_NAME: str = "Playbook KB Pipeline"
    KB_TIMEOUT: int = 30

    # Retrieval tuning
    KB_MAX_DOCS: int = 10
    KB_SCORE_THRESHOLD: float = 0.7
    KB_CONTEXT_MAX_TOKENS: int = 4000

    # Resilience
    KB_RETRY_ATTEMPTS: int = 3
    KB_RETRY_BACKOFF_BASE: int = 2  # Linear step in seconds (2s, 4s, 6s, ...)
    KB_RETRY_BACKOFF_CAP: int = 10  # Max delay between retries

    # --- Agents ----------------------------------------------------------------
    AGENT_GRAPH_RECURSION_LIMIT: int = 25
    AGENT_MAX_RETRIES: int = 3
    AGENT_RETRY_BACKOFF: float = 2.0  # Initial backoff (seconds, exponential)
    CHECKPOINT_RETENTION_DAYS: int = 30
    ATHLETE_CHAT_HISTORY_LIMIT: int = 20
    ATHLETE_CHAT_MAX_CITATIONS: int = 5
    DASHBOARD_INSIGHTS_CONTEXT_MAX_TOKENS: int = Field(default=4000, ge=1000)
    DASHBOARD_INSIGHTS_MAX_QUERY_EXAMPLES: int = Field(default=50, ge=1, le=200)
    DASHBOARD_ANALYTICS_MAX_QUERY_ROWS: int = Field(default=5000, ge=100, le=20000)
    DASHBOARD_INSIGHTS_MAX_WINDOW_DAYS: int = Field(default=30, ge=1, le=366)
    ADMIN_CHAT_HISTORY_LIMIT: int = Field(default=20, ge=1, le=100)
    ADMIN_CHAT_CONTEXT_MAX_TOKENS: int = Field(default=4000, ge=1000)
    ADMIN_CHAT_MAX_QUERY_EXAMPLES: int = Field(default=50, ge=1, le=200)
    ADMIN_CHAT_MAX_DASHBOARD_INSIGHTS: int = Field(default=5, ge=1, le=20)
    ADMIN_CHAT_MAX_REFERENCES: int = Field(default=8, ge=1, le=20)
    DASHBOARD_INSIGHTS_NIGHTLY_ENABLED: bool = True
    DASHBOARD_INSIGHTS_NIGHTLY_HOUR_UTC: int = Field(default=2, ge=0, le=23)
    DASHBOARD_INSIGHTS_NIGHTLY_MINUTE_UTC: int = Field(default=15, ge=0, le=59)
    DASHBOARD_INSIGHTS_NIGHTLY_WINDOW_DAYS: int = Field(default=7, ge=1, le=366)

    # --- Observability ---------------------------------------------------------
    TRACING_ENABLED: bool = False

    # Langfuse — runtime LLM tracing plus eval dataset/score sync.
    LANGFUSE_ENABLED: bool = False
    LANGFUSE_SECRET_KEY: str = Field(default="", repr=False)
    LANGFUSE_PUBLIC_KEY: str = ""
    LANGFUSE_HOST: str = "https://cloud.langfuse.com"

    # --- Validators ------------------------------------------------------------

    @field_validator("CORS_ORIGINS", mode="before")
    @classmethod
    def parse_cors_origins(cls, v: Any) -> list[str]:
        """Accept JSON-list or comma-separated CORS origins from env files."""
        if isinstance(v, list):
            return [str(origin).strip() for origin in v if str(origin).strip()]
        if isinstance(v, str):
            value = v.strip()
            if not value:
                return []
            if value.startswith("["):
                parsed = json.loads(value)
                if not isinstance(parsed, list):
                    raise ValueError("CORS_ORIGINS must be a list")
                return [str(origin).strip() for origin in parsed if str(origin).strip()]
            return [origin.strip() for origin in value.split(",") if origin.strip()]
        raise ValueError("CORS_ORIGINS must be a list or comma-separated string")

    @field_validator("DEBUG", mode="before")
    @classmethod
    def parse_debug(cls, v: Any) -> bool:
        """Parse common boolean/debug strings from local shells and env files."""
        if isinstance(v, bool):
            return v
        if isinstance(v, str):
            value = v.strip().lower()
            if value in {"1", "true", "yes", "on", "debug"}:
                return True
            if value in {"0", "false", "no", "off", "release", "prod", "production"}:
                return False
        return v

    @model_validator(mode="after")
    def validate_environment(self) -> "Settings":
        """Validate cross-field settings that depend on selected modes."""
        errors: list[str] = []
        is_production = _is_production_environment(self.ENVIRONMENT)

        if self.LLM_PROVIDER_MODE == "litellm":
            if not self.LITELLM_BASE_URL:
                errors.append("LITELLM_BASE_URL is required when LLM_PROVIDER_MODE=litellm")
            if not self.LITELLM_API_KEY:
                errors.append("LITELLM_API_KEY is required when LLM_PROVIDER_MODE=litellm")

        if self.LLM_PROVIDER_MODE == "direct":
            provider_key = {
                "anthropic": ("ANTHROPIC_API_KEY", self.ANTHROPIC_API_KEY),
                "openai": ("OPENAI_API_KEY", self.OPENAI_API_KEY),
                "google": ("GEMINI_API_KEY", self.GEMINI_API_KEY),
            }[self.LLM_DIRECT_PROVIDER]
            if not provider_key[1]:
                errors.append(
                    f"{provider_key[0]} is required when "
                    f"LLM_PROVIDER_MODE=direct and LLM_DIRECT_PROVIDER={self.LLM_DIRECT_PROVIDER}"
                )

        if is_production:
            if self.SECRET_KEY in ("change-me", "change-me-in-production"):
                errors.append("SECRET_KEY must be changed in production")
            if self.OAUTH_STATE_SECRET in ("change-me", "change-me-oauth-state"):
                errors.append("OAUTH_STATE_SECRET must be changed in production")
            _require_min_secret_length(errors, name="SECRET_KEY", value=self.SECRET_KEY)
            _require_min_secret_length(
                errors,
                name="OAUTH_STATE_SECRET",
                value=self.OAUTH_STATE_SECRET,
            )
            _require_min_secret_length(
                errors,
                name="KB_API_SECRET",
                value=self.KB_API_SECRET,
            )
            _require_min_secret_length(
                errors,
                name="KB_WEBHOOK_SECRET",
                value=self.KB_WEBHOOK_SECRET,
            )
            if "*" in self.CORS_ORIGINS:
                errors.append("CORS_ORIGINS cannot contain '*' in production")
            if _is_local_url(self.FRONTEND_URL):
                errors.append("FRONTEND_URL cannot use localhost in production")
            if _is_local_url(self.API_PUBLIC_URL):
                errors.append("API_PUBLIC_URL cannot use localhost in production")
            if self.LLM_PROVIDER_MODE == "litellm" and _is_local_url(
                self.LITELLM_BASE_URL
            ):
                errors.append("LITELLM_BASE_URL cannot use localhost in production")

        if self.DEV_AUTH_ENABLED and not self.dev_auth_available():
            errors.append(
                "DEV_AUTH_ENABLED can only be true in local/development debug mode"
            )

        if errors:
            raise ValueError("; ".join(errors))
        return self

    def dev_auth_available(self) -> bool:
        """Whether local-development auth bootstrap routes may be registered."""
        return (
            self.DEV_AUTH_ENABLED
            and self.DEBUG
            and self.ENVIRONMENT.lower() in {"local", "development"}
        )

    model_config = SettingsConfigDict(
        env_file=".env",
        extra="ignore",
        hide_input_in_errors=True,
    )


_settings_override: Settings | None = None


@lru_cache(maxsize=1)
def _load_settings() -> Settings:
    """Load runtime settings from the configured Pydantic sources."""
    return Settings()


def get_settings() -> Settings:
    """Return application settings, honoring a test-installed override."""
    if _settings_override is not None:
        return _settings_override
    return _load_settings()


def set_settings_override(app_settings: Settings | None) -> None:
    """Install or clear an explicit settings object for tests and app factories."""
    global _settings_override
    _settings_override = app_settings
    clear_settings_cache()


def clear_settings_cache() -> None:
    """Clear cached runtime settings."""
    _load_settings.cache_clear()


def get_request_settings(request: Request) -> Settings:
    """Return settings attached to the FastAPI app, falling back to runtime config."""
    app_settings = getattr(request.app.state, "settings", None)
    if isinstance(app_settings, Settings):
        return app_settings
    return get_settings()
