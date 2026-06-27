"""Watchdog task for recovering stuck KB embedding runs."""
from __future__ import annotations

import structlog

from app.workers.app import kb_worker

logger = structlog.get_logger(__name__)

# ---------------------------------------------------------------------------
# Watchdog — covers corner cases where the last-batch-dispatch in
# embed_batch_task never runs (worker crash before INCR, Redis INCR failure,
# unanticipated MaxRetriesExceededError path). For any document whose embed has
# been STARTED but never finalized for > N minutes, dispatch load_vector_task.
# ---------------------------------------------------------------------------
_STUCK_EMBED_MINUTES_DEFAULT = 5


@kb_worker.task(bind=True, name="app.workers.tasks.reconcile_stuck_embeds", max_retries=0)
def reconcile_stuck_embeds(self, stuck_minutes: int = _STUCK_EMBED_MINUTES_DEFAULT) -> dict:
    """Find docs stuck mid-embed and re-dispatch load_vector_task for them.

    Returns a summary {scanned, dispatched, doc_ids, stuck_minutes}.

    Stuck definition:
      embed_status = 'STARTED'        (embed phase began)
      AND load_vector_status IS NULL  (never finalized)
      AND updated_at < NOW() - stuck_minutes
    """
    from sqlalchemy import text

    from app.infrastructure.db.session import get_session_factory
    from app.workers.app import run_async

    async def _run() -> dict:
        session_factory = get_session_factory()
        async with session_factory() as session:
            result = await session.execute(
                text(
                    """
                    SELECT l.document_id, d.configuration_id
                    FROM kb.ingestion_logs l
                    JOIN kb.documents d ON d.id = l.document_id
                    WHERE l.embed_status = 'STARTED'
                      AND l.load_vector_status IS NULL
                      AND l.updated_at < (NOW() AT TIME ZONE 'UTC') - (:mins * INTERVAL '1 minute')
                    ORDER BY l.updated_at ASC
                    LIMIT 50
                    """
                ),
                {"mins": stuck_minutes},
            )
            rows = result.fetchall()

        from app.workers.tasks.finalize import load_vector_task

        dispatched: list[str] = []
        for row in rows:
            document_id = str(row[0])
            config_id = str(row[1])
            try:
                load_vector_task.apply_async(
                    kwargs={"document_id": document_id, "config_id": config_id},
                )
                dispatched.append(document_id)
                logger.info(
                    "kb_watchdog_dispatched_load_vector",
                    document_id=document_id,
                    config_id=config_id,
                )
            except Exception as exc:
                logger.warning(
                    "kb_watchdog_dispatch_failed", document_id=document_id, error=str(exc)
                )

        summary = {
            "scanned": len(rows),
            "dispatched": len(dispatched),
            "doc_ids": dispatched,
            "stuck_minutes": stuck_minutes,
        }
        logger.info("kb_watchdog_completed", **summary)
        return summary

    return run_async(_run())
