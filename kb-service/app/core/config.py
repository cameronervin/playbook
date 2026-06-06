"""KB Service settings — loaded from environment variables.

Grouped by concern. Mode-dependent required fields are enforced in
``_validate_provider_config``. Genericized scaffold: OCR is a stub
(``OCR_PROVIDER="none"``); plug Textract/VLM back in via the OCR provider
(see ``app/infrastructure/STUBS.md``).
"""
from __future__ import annotations

from typing import Literal

from pydantic import model_validator
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # -------------------------------------------------------------------------
    # Database — async driver (postgresql+asyncpg://...). Models live in the
    # dedicated ``kb`` schema so this can share a Postgres instance with the
    # main app while staying isolated.
    # -------------------------------------------------------------------------
    DATABASE_URL: str  # must be provided

    # -------------------------------------------------------------------------
    # Celery / Valkey — dedicated broker + result backend for the ingest pipeline
    # -------------------------------------------------------------------------
    CELERY_BROKER_URL: str = "redis://kb-valkey:6379/0"
    CELERY_RESULT_BACKEND: str = "redis://kb-valkey:6379/1"

    # -------------------------------------------------------------------------
    # Embedding provider mode — gateway | direct
    #   gateway: routes through a LiteLLM endpoint (production)
    #   direct:  calls the OpenAI API directly with OPENAI_API_KEY (dev/test)
    # -------------------------------------------------------------------------
    KB_LLM_PROVIDER_MODE: str = "direct"

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

    # direct mode — OPENAI_API_KEY required
    OPENAI_API_KEY: str = ""
    OPENAI_EMBED_MODEL: str = "text-embedding-3-small"

    # gateway mode — LLM_GATEWAY_BASE_URL + LLM_GATEWAY_API_KEY required
    LLM_GATEWAY_BASE_URL: str = ""
    LLM_GATEWAY_API_KEY: str = ""
    LLM_GATEWAY_EMBED_MODEL: str = "text-embedding-3-small"

    # -------------------------------------------------------------------------
    # S3-compatible storage — where original uploads + staged NDJSON live
    # -------------------------------------------------------------------------
    AWS_S3_BUCKET: str = "kb-documents"
    AWS_S3_ENDPOINT_URL: str = ""  # empty = real AWS; set to MinIO URL for local dev
    AWS_REGION: str = "us-east-1"
    AWS_ACCESS_KEY_ID: str = ""
    AWS_SECRET_ACCESS_KEY: str = ""
    AWS_PROFILE: str = ""  # named profile; used when explicit keys are not set

    # -------------------------------------------------------------------------
    # Webhook — status push from KB → the calling app (HMAC-SHA256 signed)
    # -------------------------------------------------------------------------
    APP_WEBHOOK_URL: str = "http://localhost:8000"  # base URL, no trailing slash
    KB_WEBHOOK_SECRET: str  # HMAC-SHA256 shared secret; must be provided
    KB_WEBHOOK_MAX_RETRIES: int = 5
    KB_WEBHOOK_BACKOFF_BASE: int = 2   # 2s → 8s → 32s → 120s → 120s

    # -------------------------------------------------------------------------
    # Service-to-service auth — caller → KB API (Bearer token)
    # -------------------------------------------------------------------------
    KB_API_SECRET: str  # Bearer token callers must supply; must be provided

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
    #   OCR_PROVIDER="none" → NullOCRProvider (stub). High-complexity/scanned
    #   PDFs fall back to the local text parser. Set to "textract" or "vlm" only
    #   after implementing those providers (see app/infrastructure/STUBS.md).
    # -------------------------------------------------------------------------
    OCR_PROVIDER: Literal["none", "textract", "vlm"] = "none"
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
        if self.KB_LLM_PROVIDER_MODE == "direct" and not self.OPENAI_API_KEY:
            raise ValueError("OPENAI_API_KEY is required when KB_LLM_PROVIDER_MODE=direct")
        if self.KB_LLM_PROVIDER_MODE == "gateway" and not self.LLM_GATEWAY_BASE_URL:
            raise ValueError("LLM_GATEWAY_BASE_URL is required when KB_LLM_PROVIDER_MODE=gateway")
        if self.KB_LLM_PROVIDER_MODE == "gateway" and not self.LLM_GATEWAY_API_KEY:
            raise ValueError("LLM_GATEWAY_API_KEY is required when KB_LLM_PROVIDER_MODE=gateway")
        return self

    model_config = {"env_file": ".env", "case_sensitive": False, "extra": "ignore"}


settings = Settings()
