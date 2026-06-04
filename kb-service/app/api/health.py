"""GET /api/kb/health — liveness + readiness probe.

Returns {"status": "ok"} when both Postgres and Valkey (Celery broker) are
reachable. Returns {"status": "degraded"} with per-check detail when either is
not. No auth required — this endpoint is intentionally public so infra probes
can reach it without credentials.
"""
from __future__ import annotations

import structlog
from fastapi import APIRouter

from app.core.config import settings
from app.infrastructure.db.session import get_engine
from app.repositories.system_repo import SystemRepository

logger = structlog.get_logger(__name__)

router = APIRouter()

_PROBE_TIMEOUT = 3.0  # seconds — fail fast on dependency outage


async def _check_postgres() -> tuple[str, str]:
    """Return ('postgres', 'ok') or ('postgres', 'error: <msg>')."""
    try:
        await SystemRepository(get_engine()).ping_db()
        return "postgres", "ok"
    except Exception as exc:
        logger.warning("kb_health_postgres_probe_failed", error=str(exc))
        return "postgres", f"error: {exc}"


async def _check_valkey() -> tuple[str, str]:
    """Return ('valkey', 'ok') or ('valkey', 'error: <msg>')."""
    try:
        from redis import asyncio as aioredis  # lazy: not always available in test env
    except ImportError:
        return "valkey", "error: redis package not installed"

    client = aioredis.from_url(
        settings.CELERY_BROKER_URL,
        socket_connect_timeout=_PROBE_TIMEOUT,
        socket_timeout=_PROBE_TIMEOUT,
    )
    try:
        await client.ping()
        return "valkey", "ok"
    except Exception as exc:
        logger.warning("kb_health_valkey_probe_failed", error=str(exc))
        return "valkey", f"error: {exc}"
    finally:
        await client.aclose()


@router.get("", tags=["health"])
async def health_check() -> dict:
    """Liveness + readiness probe.

    Probes Postgres (SELECT 1) and Valkey (PING).
    status=ok  → both reachable.
    status=degraded → at least one probe failed.
    """
    results = dict([await _check_postgres(), await _check_valkey()])
    overall = "ok" if all(v == "ok" for v in results.values()) else "degraded"
    if overall == "degraded":
        logger.error("kb_health_degraded", checks=results)
    return {"status": overall, "checks": results}
