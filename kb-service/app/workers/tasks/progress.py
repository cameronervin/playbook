"""Redis-backed embed progress counter helpers."""
from __future__ import annotations

import structlog

logger = structlog.get_logger(__name__)

# ---------------------------------------------------------------------------
# Embed progress counter — replaces Celery's chord_unlock for tracking completion.
# Stored in the Celery result-backend Redis so it shares the connection pool.
# ---------------------------------------------------------------------------
_EMBED_PROGRESS_TTL_SECONDS = 86400  # 24h — far longer than any real pipeline


def _embed_progress_key(document_id: str) -> str:
    return f"kb:embed_progress:{document_id}"


def _get_result_backend_client():
    """Return the raw redis client used by the result backend (lazy — no import-time conn)."""
    from celery import current_app

    return current_app.backend.client


def reset_embed_progress(document_id: str) -> None:
    """Clear the per-document batch completion counter. Called at embed_task start."""
    try:
        _get_result_backend_client().delete(_embed_progress_key(document_id))
    except Exception as exc:
        logger.warning("kb_embed_progress_reset_failed", document_id=document_id, error=str(exc))


def get_embed_progress(document_id: str) -> int:
    """Read the per-document batch completion counter without incrementing it.

    Used by load_vector_task's smart-defer check: if ``progress < total`` the
    embed phase is still in flight and we must NOT reissue. Returns 0 if the key
    does not exist or Redis is unreachable.
    """
    try:
        client = _get_result_backend_client()
        value = client.get(_embed_progress_key(document_id))
        if value is None:
            return 0
        return int(value)
    except Exception as exc:
        logger.warning("kb_embed_progress_get_failed", document_id=document_id, error=str(exc))
        return 0


def increment_embed_progress(document_id: str) -> int:
    """Atomically increment the counter and return the new value.

    Returns 0 on Redis failure so the last-batch dispatch path is skipped — the
    safety-net (load_vector self-check) will still close the loop.
    """
    try:
        client = _get_result_backend_client()
        key = _embed_progress_key(document_id)
        new_value = client.incr(key)
        client.expire(key, _EMBED_PROGRESS_TTL_SECONDS)
        return int(new_value)
    except Exception as exc:
        logger.warning("kb_embed_progress_incr_failed", document_id=document_id, error=str(exc))
        return 0


# ---------------------------------------------------------------------------
