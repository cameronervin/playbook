"""Application settings.

Pydantic Settings with environment-driven configuration. Sections preserved
from the production pattern: app, database, security/JWT, CORS, LLM provider
mode (gateway/direct), KB provider mode (local/mock), S3 storage, LangGraph
checkpoint, and Celery task queue. Domain-specific budgets have been removed —
add product-specific settings in their own section as the app grows.
"""
from pydantic import ConfigDict, ValidationInfo, field_validator
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # =========================================================================
    # App
    # =========================================================================
    PROJECT_NAME: str = "Agentic App Scaffold"
    ENVIRONMENT: str = "local"
    DEBUG: bool = True
    LOG_LEVEL: str = "DEBUG"

    # =========================================================================
    # Database — must come from environment
    # =========================================================================
    DATABASE_URL: str = "postgresql+asyncpg://app:app@localhost:5432/app"

    # LangGraph checkpoint database (optional — defaults to DATABASE_URL).
    LANGGRAPH_CHECKPOINT_DB_URL: str | None = None

    # =========================================================================
    # Security / JWT
    # =========================================================================
    SECRET_KEY: str = "change-me-in-production"
    CORS_ORIGINS: list[str] = ["http://localhost:5173"]
    FRONTEND_URL: str = "http://localhost:5173"

    JWT_LIFETIME_SECONDS: int = 3600  # 1 hour
    JWT_REFRESH_THRESHOLD_SECONDS: int = 1800  # Renew if < 30 min remaining
    # Cookie domain: "" or "localhost" for local dev, ".example.com" for prod.
    COOKIE_DOMAIN: str = "localhost"

    # =========================================================================
    # LLM Provider Mode
    # =========================================================================
    # "gateway" = route every request through a LiteLLM gateway (OpenAI-compatible)
    # "direct"  = per-use-case provider selection with direct SDK access
    LLM_PROVIDER_MODE: str = "direct"

    # --- Gateway mode (when LLM_PROVIDER_MODE=gateway) ---
    LLM_GATEWAY_BASE_URL: str = "http://localhost:4000"
    LLM_GATEWAY_API_KEY: str = ""
    # Model aliases as registered on the gateway. Default to Claude ids.
    LLM_CHAT_MODEL: str = "claude-sonnet-4-6"
    LLM_RESEARCH_MODEL: str = "claude-opus-4-8"

    # --- Direct mode (when LLM_PROVIDER_MODE=direct) ---
    # Provider options: "anthropic" | "openai" | "google" | "gateway"
    # Anthropic-first defaults.
    CHAT_PROVIDER: str = "anthropic"
    CHAT_MODEL: str = "claude-sonnet-4-6"
    # Research / advanced tier (high-capability model for deep reasoning).
    RESEARCH_PROVIDER: str = "anthropic"
    ADVANCED_MODEL: str = "claude-opus-4-8"

    # --- Common LLM settings (all modes) ---
    LLM_TEMPERATURE: float = 0.2
    LLM_MAX_TOKENS: int = 16384
    LLM_TIMEOUT: int = 600

    # --- API keys (required based on provider selection) ---
    ANTHROPIC_API_KEY: str | None = None
    OPENAI_API_KEY: str | None = None
    GEMINI_API_KEY: str | None = None

    # =========================================================================
    # Knowledgebase Provider Mode
    # =========================================================================
    # Provider mode: local | mock (see knowledgebase.factory.KBProviderMode).
    KB_PROVIDER_MODE: str = "mock"
    # Feature flag — set false to detach KB tools entirely.
    KB_ENABLED: bool = True

    # Local KB service connection (only used when KB_PROVIDER_MODE=local).
    KB_LOCAL_BASE_URL: str = "http://kb-api:8001"
    KB_API_SECRET: str = ""  # Bearer token sent with every call to the KB service
    KB_CONFIG_NAME: str = "Scaffold KB Pipeline"
    KB_TIMEOUT: int = 30

    # Retrieval tuning.
    KB_MAX_DOCS: int = 10
    KB_SCORE_THRESHOLD: float = 0.7
    KB_CONTEXT_MAX_TOKENS: int = 4000

    # Resilience.
    KB_RETRY_ATTEMPTS: int = 3
    KB_RETRY_BACKOFF_BASE: int = 2  # Linear step in seconds (2s, 4s, 6s, ...)
    KB_RETRY_BACKOFF_CAP: int = 10  # Max delay between retries

    # =========================================================================
    # S3 Storage
    # =========================================================================
    # Set S3_ENDPOINT_URL to a LocalStack URL (e.g. http://localstack:4566) for
    # local/dev. Leave empty/None for production AWS S3.
    S3_ENDPOINT_URL: str | None = None
    S3_BUCKET_NAME: str = "scaffold-bucket"
    S3_REGION: str = "us-east-1"
    # Explicit credentials (LocalStack: S3_ACCESS_KEY_ID=test). If unset, boto3
    # falls back to AWS_PROFILE, then the default credential chain / IAM role.
    S3_ACCESS_KEY_ID: str | None = None
    S3_SECRET_ACCESS_KEY: str | None = None
    AWS_PROFILE: str | None = None
    S3_TIMEOUT: int = 120
    S3_PRESIGNED_URL_EXPIRY: int = 3600

    # =========================================================================
    # LangGraph Agent Settings
    # =========================================================================
    AGENT_GRAPH_RECURSION_LIMIT: int = 25
    AGENT_MAX_RETRIES: int = 3
    AGENT_RETRY_BACKOFF: float = 2.0  # Initial backoff (seconds, exponential)
    CHECKPOINT_RETENTION_DAYS: int = 30

    # =========================================================================
    # Celery + Valkey/Redis (Task Queue)
    # =========================================================================
    CELERY_BROKER_URL: str = "redis://localhost:6379/0"
    CELERY_RESULT_BACKEND: str = "redis://localhost:6379/1"
    CELERY_TASK_SOFT_TIME_LIMIT: int = 600  # 10 min
    CELERY_TASK_HARD_TIME_LIMIT: int = 660
    CELERY_TASK_MAX_RETRIES: int = 3
    CELERY_TASK_RETRY_COUNTDOWN: int = 60  # seconds before retry

    # =========================================================================
    # Observability (optional)
    # =========================================================================
    TRACING_ENABLED: bool = False

    # -------------------------------------------------------------------------
    # Validators
    # -------------------------------------------------------------------------

    @field_validator("SECRET_KEY")
    @classmethod
    def validate_secret_key(cls, v: str, info: ValidationInfo) -> str:
        """Ensure SECRET_KEY is changed in production."""
        env = info.data.get("ENVIRONMENT", "")
        if env == "production" and v in ("change-me", "change-me-in-production"):
            raise ValueError("SECRET_KEY must be changed in production")
        return v

    @field_validator("LLM_GATEWAY_BASE_URL")
    @classmethod
    def validate_llm_gateway_url(cls, v: str, info: ValidationInfo) -> str:
        """Ensure LLM_GATEWAY_BASE_URL is not localhost in production."""
        env = info.data.get("ENVIRONMENT", "")
        if env == "production" and ("localhost" in v or "127.0.0.1" in v):
            raise ValueError(
                "LLM_GATEWAY_BASE_URL cannot use localhost in production. "
                "Set a valid gateway URL in environment variables."
            )
        return v

    model_config = ConfigDict(env_file=".env", extra="ignore")


settings = Settings()
