"""Webhook status and safe metadata helpers for KB document mirroring."""

from __future__ import annotations

from typing import Any, Protocol
from uuid import UUID

from app.core.log_redaction import redact_string

_TERMINAL_READY = {"success", "succeeded", "complete", "completed", "ready"}
_TERMINAL_FAILED = {"failure", "failed", "error", "revoked"}
_PROCESSING = {"started", "processing", "parsing", "chunking", "embedding", "loading"}


class _AdminWebhookIdentity(Protocol):
    kb_service_document_id: UUID | None
    source_type: str | None
    playbook_document_id: UUID | None
    document_id: UUID


def map_kb_webhook_status(raw_status: str, stage: str | None) -> str:
    """Map KB-service status/stage values onto backend document statuses."""
    status = raw_status.lower()
    normalized_stage = (stage or "").lower()
    if status == "ready":
        return "ready"
    if normalized_stage in {"", "pipeline"} and status in _TERMINAL_READY:
        return "ready"
    if status in _TERMINAL_FAILED or (
        normalized_stage == "pipeline" and status == "failed"
    ):
        return "failed"
    if status in _PROCESSING or status == "success":
        return "processing"
    if status == "pending":
        return "uploaded"
    return "processing"


def chunk_count_from_metadata(metadata: dict[str, Any]) -> int | None:
    """Return a safe non-negative chunk count from webhook metadata."""
    raw_count = metadata.get("chunk_count")
    if isinstance(raw_count, bool) or not isinstance(raw_count, int):
        return None
    if raw_count < 0:
        return None
    return raw_count


def admin_kb_service_document_id(payload: _AdminWebhookIdentity) -> UUID | None:
    """Resolve the KB-service document ID for admin-upload webhook mirroring."""
    if payload.kb_service_document_id is not None:
        return payload.kb_service_document_id
    if payload.source_type == "admin_upload" and payload.playbook_document_id is not None:
        return payload.document_id
    return None


def document_kb_service_document_id(document: object) -> str | None:
    """Return a string KB-service document ID from an ORM-like document."""
    kb_service_document_id = getattr(document, "kb_service_document_id", None)
    return str(kb_service_document_id) if kb_service_document_id else None


def sanitize_failure_reason(message: str | None) -> str | None:
    """Redact and bound a KB-service failure reason before persistence."""
    if message is None:
        return None
    redacted = redact_string(message)
    if "http://" in redacted or "https://" in redacted:
        return "KB ingestion failed"
    return redacted[:500]
