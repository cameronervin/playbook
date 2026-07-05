"""KB Service — FastAPI entry point.

Exposes the KB API under /api/kb (see app/api/router.py). Status webhooks flow
outbound: KB → the calling app via HMAC-signed POST.
"""
from __future__ import annotations

from contextlib import asynccontextmanager
from typing import AsyncGenerator

import structlog
from fastapi import FastAPI
from starlette.middleware.cors import CORSMiddleware

from app.core.config import Settings, settings
from app.core.logging_config import configure_logging
from app.infrastructure.db.session import cleanup_db_engine
from app.observability.sentry_init import init_sentry

configure_logging(settings.LOG_LEVEL)
init_sentry(settings, service_name="kb-api", include_fastapi=True)
logger = structlog.get_logger(__name__)


def _is_production_environment(value: str) -> bool:
    return value.lower() in {"prod", "production"}


def _parse_cors_origins(value: str) -> list[str]:
    return [origin.strip() for origin in value.split(",") if origin.strip()]


def docs_urls_for_settings(app_settings: Settings) -> dict[str, str | None]:
    """Return FastAPI docs/OpenAPI URLs for the current environment."""
    if _is_production_environment(app_settings.ENVIRONMENT):
        return {"openapi_url": None, "docs_url": None, "redoc_url": None}
    return {"openapi_url": "/openapi.json", "docs_url": "/docs", "redoc_url": None}


def cors_origins_for_settings(app_settings: Settings) -> list[str]:
    """Return explicit CORS origins, keeping wildcard only for non-production."""
    configured = _parse_cors_origins(app_settings.CORS_ORIGINS)
    if configured:
        return configured
    if _is_production_environment(app_settings.ENVIRONMENT):
        return []
    return ["*"]


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator:
    logger.info("kb_service_startup", environment=settings.ENVIRONMENT)
    # Lazy import: the embedders factory pulls in heavy deps (openai) built by
    # another agent — keep it out of module import time.
    from app.infrastructure.embedders.factory import get_embed_provider

    app.state.embed_provider = get_embed_provider()
    yield
    from app.infrastructure.rerankers.factory import (
        clear_all_caches as clear_rerank_caches,
    )

    clear_rerank_caches()
    await cleanup_db_engine()
    logger.info("kb_service_shutdown")


app = FastAPI(
    title=settings.PROJECT_NAME,
    lifespan=lifespan,
    **docs_urls_for_settings(settings),
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origins_for_settings(settings),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Import router here (deferred to avoid circular imports at module load)
from app.api.router import api_router  # noqa: E402

app.include_router(api_router, prefix="/api/kb")


@app.get("/health", tags=["health"], include_in_schema=False)
async def health_root() -> dict:
    """Root liveness alias for the container healthcheck — forwards to /api/kb/health."""
    from app.api.health import health_check

    return await health_check()
