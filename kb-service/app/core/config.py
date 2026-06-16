"""KB Service settings — loaded from environment variables.

Grouped by concern. Mode-dependent required fields are enforced in
``_validate_provider_config``. OCR is opt-in: ``OCR_PROVIDER="none"`` by
default, while ``OCR_PROVIDER="vlm"`` routes scanned PDF OCR through LiteLLM.
"""
from __future__ import annotations

from typing import Literal

from pydantic import Field, model_validator
from pydantic_settings import BaseSettings


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
    # -------------------------------------------------------------------------
    # Database — async driver (postgresql+asyncpg://...). Models live in the
    # dedicated ``kb`` schema so this can share a Postgres instance with the
    # main app while staying isolated.
    # -------------------------------------------------------------------------
    DATABASE_URL: str = Field(repr=False)  # must be provided

    # -------------------------------------------------------------------------
    # Celery / Valkey — dedicated broker + result backend for the ingest pipeline
    # -------------------------------------------------------------------------
    CELERY_BROKER_URL: str = Field(default="redis://kb-valkey:6379/0", repr=False)
    CELERY_RESULT_BACKEND: str = Field(default="redis://kb-valkey:6379/1", repr=False)

    # -------------------------------------------------------------------------
    # Embedding provider mode — litellm | direct
    #   litellm: routes through a LiteLLM endpoint (production)
    #   direct:  calls the OpenAI API directly with OPENAI_API_KEY (dev/test)
    # -------------------------------------------------------------------------
    LLM_PROVIDER_MODE: Literal["direct", "litellm"] = "litellm"

    # Shared embedding tuning (applies to both modes)
    KB_EMBED_DIMENSIONS: int = 1536
    KB_EMBED_BATCH_SIZE: int = 50
    KB_EMBED_MAX_BATCH_CHARS: int = 60_000
    KB_EMBED_MAX_CONCURRENT_BATCHES: int = 4
    KB_EMBED_REQUEST_TIMEOUT_SECONDS: float = 60.0
    KB_EMBED_MAX_RETRIES: int = 5
    KB_EMBED_BACKOFF_BASE_SECONDS: int = 2
    KB_EMBED_BACKOFF_MAX_SECONDS: int = 120
    KB_EMBED_RETRY_JITTER: bool = True

    # direct mode — OPENAI_API_KEY required. The direct model is fixed because
    # normal deployments should configure provider model IDs only in LiteLLM.
    OPENAI_API_KEY: str = Field(default="", repr=False)
    DIRECT_EMBED_MODEL: str = "text-embedding-3-small"

    # litellm mode — LITELLM_BASE_URL + LITELLM_API_KEY required
    LITELLM_BASE_URL: str = ""
    LITELLM_API_KEY: str = Field(default="", repr=False)
    LITELLM_EMBED_MODEL: str = "playbook-embed"
    LITELLM_VLM_MODEL: str = "playbook-ocr"

    # -------------------------------------------------------------------------
    # S3-compatible storage — where original uploads + staged NDJSON live
    # -------------------------------------------------------------------------
    S3_BUCKET_NAME: str = "playbook-bucket"
    S3_ENDPOINT_URL: str = ""  # empty = real AWS; set to MinIO URL for local dev
    S3_REGION: str = "us-east-1"
    S3_ACCESS_KEY_ID: str = Field(default="", repr=False)
    S3_SECRET_ACCESS_KEY: str = Field(default="", repr=False)
    AWS_PROFILE: str = ""  # named profile; used when explicit keys are not set

    # -------------------------------------------------------------------------
    # Webhook — status push from KB → the calling app (HMAC-SHA256 signed)
    # -------------------------------------------------------------------------
    APP_WEBHOOK_URL: str = "http://localhost:8000"  # base URL, no trailing slash
    KB_WEBHOOK_SECRET: str = Field(repr=False)  # HMAC-SHA256 shared secret; must be provided
    KB_WEBHOOK_MAX_RETRIES: int = 5
    KB_WEBHOOK_BACKOFF_BASE: int = 2   # 2s → 8s → 32s → 120s → 120s

    # -------------------------------------------------------------------------
    # Service-to-service auth — caller → KB API (Bearer token)
    # -------------------------------------------------------------------------
    KB_API_SECRET: str = Field(repr=False)  # Bearer token callers must supply; must be provided

    # -------------------------------------------------------------------------
    # Service metadata
    # -------------------------------------------------------------------------
    PROJECT_NAME: str = "KB Service"
    ENVIRONMENT: str = "local"
    LOG_LEVEL: Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"] = "INFO"

    # -------------------------------------------------------------------------
    # Chunking — changing these requires re-ingesting existing documents
    # -------------------------------------------------------------------------
    KB_CHUNK_SIZE_TOKENS: int = 400
    KB_CHUNK_OVERLAP_TOKENS: int = 40
    KB_CHUNK_TOKENIZER: str = "cl100k_base"

    # -------------------------------------------------------------------------
    # Search defaults
    # -------------------------------------------------------------------------
    KB_SEARCH_MAX_DOCS: int = 10
    KB_SEARCH_SCORE_THRESHOLD: float = 0.7

    # -------------------------------------------------------------------------
    # Worker / vectorstore tuning
    # -------------------------------------------------------------------------
    KB_VECTORSTORE_POOL_SIZE: int = 5       # SQLAlchemy sync engine pool per worker process
    KB_VECTOR_INSERT_BATCH_SIZE: int = 500  # rows per INSERT batch in load_vector_task

    # -------------------------------------------------------------------------
    # Parser routing
    #   OCR_PROVIDER="none" → NullOCRProvider. High-complexity/scanned PDFs fall
    #   back to the local text parser. OCR_PROVIDER="vlm" sends scanned PDF
    #   pages through the LiteLLM vision model alias configured above.
    # -------------------------------------------------------------------------
    OCR_PROVIDER: Literal["none", "textract", "vlm"] = "none"
    VLM_OCR_DPI: int = 150
    VLM_OCR_DETAIL: Literal["auto", "low", "high"] = "high"
    VLM_OCR_MAX_PAGES: int = 50
    VLM_OCR_REQUEST_TIMEOUT_SECONDS: float = 120.0
    ENABLE_DOCLING_ROUTING: bool = True
    DOC_PARSER_POLICY: str = "complexity"   # complexity | always_docling | always_basic

    # Complexity thresholds — deterministic low/medium/high classification
    PARSE_OCR_CHARS_THRESHOLD: int = 100
    PARSE_OCR_IMAGE_RATIO_THRESHOLD: float = 0.95
    PARSE_OCR_EMPTY_PAGE_RATIO_THRESHOLD: float = 0.5
    PARSE_OCR_IMAGE_PAGE_RATIO_THRESHOLD: float = 0.3
    PDF_VERY_COMPLEX_EMPTY_PAGE_RATIO_THRESHOLD: float = 0.8
    PDF_VERY_COMPLEX_IMAGE_PAGE_RATIO_THRESHOLD: float = 0.75
    PDF_VERY_COMPLEX_PAGE_COUNT_THRESHOLD: int = 250

    DOCX_COMPLEX_TABLE_COUNT_THRESHOLD: int = 1
    DOCX_COMPLEX_INLINE_SHAPE_THRESHOLD: int = 1
    DOCX_COMPLEX_MAX_PARAGRAPH_CHARS_THRESHOLD: int = 300

    PPTX_COMPLEX_TABLE_COUNT_THRESHOLD: int = 1
    PPTX_COMPLEX_PICTURE_COUNT_THRESHOLD: int = 3
    PPTX_COMPLEX_CHART_COUNT_THRESHOLD: int = 1
    PPTX_COMPLEX_SHAPE_COUNT_THRESHOLD: int = 30

    # -------------------------------------------------------------------------
    # Docling tuning
    # -------------------------------------------------------------------------
    DOCLING_ENABLED: bool = True
    DOCLING_DO_OCR: bool = True
    DOCLING_DO_TABLE_STRUCTURE: bool = True
    DOCLING_TABLE_MODE: str = "accurate"
    DOCLING_TIMEOUT_SECONDS: float = 120.0
    DOCLING_MAX_PAGES: int = 500
    DOCLING_MAX_FILE_SIZE_MB: int = 200
    DOCLING_IMAGES_SCALE: float = 1.5
    DOCLING_TUNING_PROFILE: str = "balanced"  # balanced | speed | quality
    DOCLING_OCR_LANG: str = "en"
    DOCLING_DISABLE_OCR_FOR_LOW_COMPLEXITY: bool = False
    DOCLING_DISABLE_TABLES_FOR_LOW_COMPLEXITY: bool = False
    DOCLING_ENABLE_ACCELERATION: bool = True
    DOCLING_ACCELERATOR_DEVICE: str = "auto"  # auto | cpu | cuda | mps
    DOCLING_ACCELERATOR_THREADS: int = 4

    # -------------------------------------------------------------------------
    # S3 streaming + upload guardrails
    # -------------------------------------------------------------------------
    S3_STREAM_MAX_FILE_SIZE_MB: int = 512
    S3_STREAM_SPOOL_MAX_SIZE_MB: int = 32
    KB_MAX_DOCUMENT_SIZE_MB: int = 200

    @model_validator(mode="after")
    def _validate_provider_config(self) -> "Settings":
        errors: list[str] = []
        if self.LLM_PROVIDER_MODE == "direct" and not self.OPENAI_API_KEY:
            errors.append("OPENAI_API_KEY is required when LLM_PROVIDER_MODE=direct")
        if self.LLM_PROVIDER_MODE == "litellm" and not self.LITELLM_BASE_URL:
            errors.append(
                "LITELLM_BASE_URL is required when LLM_PROVIDER_MODE=litellm"
            )
        if self.LLM_PROVIDER_MODE == "litellm" and not self.LITELLM_API_KEY:
            errors.append(
                "LITELLM_API_KEY is required when LLM_PROVIDER_MODE=litellm"
            )
        if self.OCR_PROVIDER == "vlm":
            if not self.LITELLM_BASE_URL:
                errors.append("LITELLM_BASE_URL is required when OCR_PROVIDER=vlm")
            if not self.LITELLM_API_KEY:
                errors.append("LITELLM_API_KEY is required when OCR_PROVIDER=vlm")
            if not self.LITELLM_VLM_MODEL:
                errors.append("LITELLM_VLM_MODEL is required when OCR_PROVIDER=vlm")
        if _is_production_environment(self.ENVIRONMENT):
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
        if errors:
            raise ValueError("; ".join(errors))
        return self

    model_config = {
        "env_file": ".env",
        "case_sensitive": False,
        "extra": "ignore",
        "hide_input_in_errors": True,
    }


settings = Settings()
