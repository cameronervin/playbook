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

from app.core.config import settings
from app.core.logging_config import configure_logging
from app.infrastructure.db.session import cleanup_db_engine

configure_logging(settings.LOG_LEVEL)
logger = structlog.get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator:
    logger.info("kb_service_startup", environment=settings.ENVIRONMENT)
    # Lazy import: the embedders factory pulls in heavy deps (openai) built by
    # another agent — keep it out of module import time.
    from app.infrastructure.embedders.factory import get_embed_provider

    app.state.embed_provider = get_embed_provider()
    yield
    await cleanup_db_engine()
    logger.info("kb_service_shutdown")


app = FastAPI(
    title=settings.PROJECT_NAME,
    openapi_url="/openapi.json",
    docs_url="/docs",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
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
