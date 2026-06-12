"""Status notification task and dispatch helper for the KB pipeline."""
from __future__ import annotations

import uuid

import structlog

from app.workers.app import kb_worker

logger = structlog.get_logger(__name__)


def _notify(
    document_id: str,
    stage: str,
    status: str,
    error_message: str | None = None,
) -> None:
    """Fire-and-forget notify dispatch — broker failure must not crash the pipeline task."""
    try:
        notify_status_task.delay(
            document_id=document_id,
            stage=stage,
            status=status,
            error_message=error_message,
        )
    except Exception:
        logger.warning(
            "kb_notify_dispatch_failed",
            document_id=document_id,
            stage=stage,
            status=status,
        )


@kb_worker.task(
    bind=True,
    name="app.workers.tasks.notify_status_task",
    max_retries=5,
    default_retry_delay=2,
)
def notify_status_task(
    self,
    *,
    document_id: str,
    status: str,
    stage: str | None = None,
    error_message: str | None = None,
) -> None:
    """HMAC-SHA256 sign and POST a status update to the calling app's webhook.

    Posts to ``{settings.APP_WEBHOOK_URL}/api/v1/kb/webhook`` with an
    ``X-KB-Signature: sha256=<hex>`` header. On permanent failure (all retries
    exhausted), the delivery is dead-lettered into kb.ingestion_logs so the
    caller's reconciler can recover terminal events on its next run.
    """
    import hashlib
    import hmac
    import json
    import time as _time

    import httpx

    from app.core.config import settings

    payload = {
        "document_id": document_id,
        "stage": stage,
        "status": status,
        "error_message": error_message,
        "timestamp": int(_time.time()),
    }
    body = json.dumps(payload, separators=(",", ":")).encode()
    signature = hmac.new(
        settings.KB_WEBHOOK_SECRET.encode(),
        body,
        hashlib.sha256,
    ).hexdigest()

    url = f"{settings.APP_WEBHOOK_URL.rstrip('/')}/api/v1/kb/webhook"
    headers = {
        "Content-Type": "application/json",
        "X-KB-Signature": f"sha256={signature}",
    }
    try:
        response = httpx.post(url, content=body, headers=headers, timeout=10)
        response.raise_for_status()
        logger.info(
            "kb_webhook_sent",
            document_id=document_id,
            stage=stage,
            status=status,
            http_status=response.status_code,
        )
    except httpx.HTTPStatusError as exc:
        logger.warning(
            "kb_webhook_http_error",
            document_id=document_id,
            stage=stage,
            status=status,
            http_status=exc.response.status_code,
        )
        if self.request.retries >= self.max_retries:
            _handle_webhook_dead_letter(self.request.id, document_id, stage, status, exc)
        raise self.retry(exc=exc) from exc
    except httpx.TransportError as exc:
        logger.warning(
            "kb_webhook_transport_error",
            document_id=document_id,
            stage=stage,
            status=status,
            error=str(exc),
        )
        if self.request.retries >= self.max_retries:
            _handle_webhook_dead_letter(self.request.id, document_id, stage, status, exc)
        raise self.retry(exc=exc) from exc


def _handle_webhook_dead_letter(
    task_id: str | None,
    document_id: str | None,
    stage: str | None,
    status: str | None,
    exc: Exception,
) -> None:
    """Log dead-letter at ERROR and persist to kb.ingestion_logs.

    Called when notify_status_task exhausts all retries. The ERROR log is the
    breadcrumb hook point for future alerting.
    """
    logger.error(
        "kb_webhook_dead_lettered",
        task_id=task_id,
        document_id=document_id,
        stage=stage,
        status=status,
        error=str(exc),
        exc_info=True,
    )

    if not document_id:
        return

    from app.infrastructure.db.session import get_session_factory
    from app.workers.app import run_async

    async def _persist() -> None:
        session_factory = get_session_factory()
        async with session_factory() as session:
            from app.repositories.ingestion_log_repo import IngestionLogRepository

            try:
                doc_uuid = uuid.UUID(document_id)
            except ValueError:
                return
            log_repo = IngestionLogRepository(session)
            await log_repo.update_stage(
                doc_uuid,
                stage=stage or "notify",
                status="DEAD_LETTERED",
                error_message=f"webhook delivery exhausted retries: {exc}",
            )

    try:
        run_async(_persist())
    except Exception as persist_exc:
        logger.warning(
            "kb_webhook_dead_letter_persist_failed",
            document_id=document_id,
            error=str(persist_exc),
        )


# ---------------------------------------------------------------------------
