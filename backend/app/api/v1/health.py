"""Health and readiness checks."""

from __future__ import annotations

import asyncio

import structlog
from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse
from sqlalchemy import text

from app.core.config import Settings, get_request_settings
from app.infrastructure.db.session import get_engine
from app.infrastructure.knowledgebase import get_kb_provider, is_kb_feature_enabled

router = APIRouter(tags=["Health"])
logger = structlog.get_logger(__name__)

_PROBE_TIMEOUT_SECONDS = 3.0


@router.get("/health", summary="API health check")
async def health() -> dict[str, str]:
    return {"status": "healthy"}


@router.get("/ready", summary="API readiness check")
async def readiness(request: Request) -> JSONResponse:
    """Return 503 when traffic-serving dependencies are degraded."""
    settings = get_request_settings(request)
    checks = dict(
        [
            await _check_database(settings),
            await _check_kb_provider(request, settings),
        ]
    )
    overall = "ok" if all(value in {"ok", "disabled"} for value in checks.values()) else "degraded"
    if overall == "degraded":
        logger.error("backend_readiness_degraded", checks=checks)
        return JSONResponse(
            status_code=503,
            content={"status": overall, "checks": checks},
        )
    return JSONResponse(content={"status": overall, "checks": checks})


async def _check_database(settings: Settings) -> tuple[str, str]:
    """Check Postgres connectivity without exposing connection details."""

    async def ping() -> None:
        engine = get_engine(settings)
        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))

    try:
        await asyncio.wait_for(ping(), timeout=_PROBE_TIMEOUT_SECONDS)
    except Exception as exc:  # noqa: BLE001 - readiness probes must catch dependency failures.
        logger.warning("backend_readiness_postgres_failed", error_type=type(exc).__name__)
        return "postgres", "error: unavailable"
    return "postgres", "ok"


async def _check_kb_provider(request: Request, settings: Settings) -> tuple[str, str]:
    """Check KB provider health when the feature is enabled."""
    if not is_kb_feature_enabled(settings):
        return "knowledgebase", "disabled"
    try:
        provider = getattr(request.app.state, "kb_provider", None) or get_kb_provider(
            app_settings=settings
        )
        healthy = await asyncio.wait_for(
            provider.health_check(),
            timeout=_PROBE_TIMEOUT_SECONDS,
        )
    except Exception as exc:  # noqa: BLE001 - readiness probes must catch dependency failures.
        logger.warning("backend_readiness_kb_failed", error_type=type(exc).__name__)
        return "knowledgebase", "error: unavailable"
    return "knowledgebase", "ok" if healthy else "error: unavailable"
