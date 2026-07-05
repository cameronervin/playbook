"""Status notification task and dispatch helper for the KB pipeline."""
from __future__ import annotations

import uuid
from typing import Any

import structlog

from app.core.log_redaction import redact_string
from app.workers.app import kb_worker

logger = structlog.get_logger(__name__)

_WEBHOOK_PATH = "/api/v1/kb/webhook"


def _notify(
    document_id: str,
    stage: str,
    status: str,
    error_message: str | None = None,
    metadata: dict[str, Any] | None = None,
) -> None:
    """Fire-and-forget notify dispatch — broker failure must not crash the pipeline task."""
    try:
        notify_status_task.delay(
            document_id=document_id,
            stage=stage,
            status=status,
            error_message=error_message,
            metadata=metadata,
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
    metadata: dict[str, Any] | None = None,
) -> None:
    """HMAC-SHA256 sign and POST a status update to the calling app's webhook.

    Posts to the per-document webhook URL stored at ingest time with an
    ``X-KB-Signature: sha256=<hex>`` header. Legacy documents without webhook
    metadata fall back to ``settings.APP_WEBHOOK_URL`` for compatibility.
    """
    import hashlib
    import hmac
    import json
    import time as _time

    import httpx

    from app.core.config import settings

    url = _load_webhook_url(document_id)
    if not url:
        logger.info(
            "kb_webhook_skipped",
            document_id=document_id,
            stage=stage,
            status=status,
        )
        return

    document_metadata, summary = _load_document_payload_context(document_id)
    payload = _build_status_payload(
        document_id=document_id,
        status=status,
        stage=stage,
        error_message=error_message,
        document_metadata=document_metadata,
        summary=summary,
        metadata=metadata,
        timestamp=int(_time.time()),
    )
    body = json.dumps(payload, separators=(",", ":")).encode()
    signature = hmac.new(
        settings.KB_WEBHOOK_SECRET.encode(),
        body,
        hashlib.sha256,
    ).hexdigest()

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
            return
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
            return
        raise self.retry(exc=exc) from exc


def _webhook_url_from_metadata(
    metadata: dict[str, Any] | None,
    *,
    fallback_base_url: str,
) -> str | None:
    """Resolve the webhook URL from document metadata.

    New documents explicitly store webhook intent. Documents created before this
    metadata existed are treated as legacy and use APP_WEBHOOK_URL.
    """
    metadata = metadata or {}
    if "webhook_enabled" in metadata:
        if not metadata.get("webhook_enabled"):
            return None
        stored_url = metadata.get("status_webhook_url")
        return str(stored_url).strip() if stored_url else None

    stored_url = metadata.get("status_webhook_url")
    if stored_url:
        return str(stored_url).strip()

    fallback = fallback_base_url.strip().rstrip("/")
    return f"{fallback}{_WEBHOOK_PATH}" if fallback else None


def _build_status_payload(
    *,
    document_id: str,
    status: str,
    stage: str | None,
    error_message: str | None,
    document_metadata: dict[str, Any] | None,
    summary: str | None,
    metadata: dict[str, Any] | None,
    timestamp: int,
) -> dict[str, Any]:
    """Build a safe signed webhook payload."""
    document_metadata = document_metadata or {}
    payload: dict[str, Any] = {
        "document_id": document_id,
        "kb_service_document_id": document_id,
        "source_type": document_metadata.get("source_type"),
        "playbook_document_id": document_metadata.get("playbook_document_id"),
        "conversation_id": document_metadata.get("conversation_id"),
        "conversation_file_id": document_metadata.get("conversation_file_id"),
        "stage": stage,
        "status": status,
        "error_message": error_message,
        "summary": summary,
        "metadata": _sanitize_metadata(metadata or {}),
        "timestamp": timestamp,
    }
    return {key: value for key, value in payload.items() if value is not None}


def _sanitize_metadata(metadata: dict[str, Any]) -> dict[str, Any]:
    sensitive_keys = {
        "source_uri",
        "presigned_url",
        "signed_url",
        "raw_text",
        "extracted_text",
        "file_contents",
        "model_input",
        "model_inputs",
    }
    sanitized: dict[str, Any] = {}
    for key, value in metadata.items():
        if key in sensitive_keys:
            continue
        if isinstance(value, dict):
            sanitized[key] = _sanitize_metadata(value)
        else:
            sanitized[key] = value
    return sanitized


def _load_webhook_url(document_id: str) -> str | None:
    from app.core.config import settings
    from app.infrastructure.db.session import get_session_factory
    from app.repositories.document_repo import DocumentRepository
    from app.workers.app import run_async

    try:
        document_uuid = uuid.UUID(document_id)
    except (TypeError, ValueError):
        return None

    async def _load() -> str | None:
        session_factory = get_session_factory()
        async with session_factory() as session:
            doc = await DocumentRepository(session).get(document_uuid)
            if doc is None:
                return None
            return _webhook_url_from_metadata(
                doc.metadata_ or {},
                fallback_base_url=settings.APP_WEBHOOK_URL,
            )

    return run_async(_load())


def _load_document_payload_context(document_id: str) -> tuple[dict[str, Any], str | None]:
    from app.infrastructure.db.session import get_session_factory
    from app.repositories.document_repo import DocumentRepository
    from app.workers.app import run_async

    try:
        document_uuid = uuid.UUID(document_id)
    except (TypeError, ValueError):
        return {}, None

    async def _load() -> tuple[dict[str, Any], str | None]:
        session_factory = get_session_factory()
        async with session_factory() as session:
            doc = await DocumentRepository(session).get(document_uuid)
            if doc is None:
                return {}, None
            return dict(doc.metadata_ or {}), doc.summary

    try:
        return run_async(_load())
    except Exception as exc:
        logger.warning(
            "kb_webhook_payload_context_load_failed",
            document_id=document_id,
            error_type=type(exc).__name__,
        )
        return {}, None


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
    raw_error = str(exc)
    sanitized_error = redact_string(raw_error)
    http_status = getattr(getattr(exc, "response", None), "status_code", None)

    logger.error(
        "kb_webhook_dead_lettered",
        task_id=task_id,
        document_id=document_id,
        stage=stage,
        status=status,
        error_type=type(exc).__name__,
        http_status=http_status,
        error=raw_error,
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
                error_message=(
                    f"webhook delivery exhausted retries: {sanitized_error}"
                ),
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
