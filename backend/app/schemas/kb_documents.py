"""Knowledge-base document schemas."""

from __future__ import annotations

from datetime import date, datetime
from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator

KBDocumentStatus = Literal["uploaded", "processing", "ready", "failed"]
KBSourceType = Literal["admin_upload", "conversation_file"]


class KBDocumentResponse(BaseModel):
    """Admin KB document metadata response."""

    id: UUID
    organization_id: UUID
    uploaded_by: UUID
    title: str
    filename: str
    content_type: str
    size_bytes: int
    processing_status: KBDocumentStatus
    failure_reason: str | None = None
    visibility_policy: dict[str, Any]
    metadata_tags: dict[str, Any]
    source_date: date | None = None
    kb_service_document_id: UUID | None = None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class KBDocumentMetadataUpdateRequest(BaseModel):
    """Partial KB document metadata update."""

    metadata_tags: dict[str, Any] | None = None
    source_date: date | None = None


class KBDocumentEventResponse(BaseModel):
    """Document lifecycle event response."""

    id: UUID
    document_id: UUID
    event_type: str
    status: str | None
    message: str | None
    metadata: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class KBWebhookPayload(BaseModel):
    """Current KB-service HMAC-signed status webhook payload."""

    document_id: UUID
    kb_service_document_id: UUID | None = None
    source_type: KBSourceType | None = None
    playbook_document_id: UUID | None = None
    conversation_id: UUID | None = None
    conversation_file_id: UUID | None = None
    stage: str | None = None
    status: str
    error_message: str | None = None
    summary: str | None = None
    timestamp: int | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)

    @field_validator("metadata", mode="before")
    @classmethod
    def strip_sensitive_metadata(cls, value: Any) -> dict[str, Any]:
        """Drop secret-bearing file fields from webhook metadata before persistence."""
        if not isinstance(value, dict):
            return {}
        return _strip_sensitive_metadata(value)


class KBWebhookResponse(BaseModel):
    """Webhook processing acknowledgement."""

    status: Literal["ok"] = "ok"
    document_status: KBDocumentStatus


def _strip_sensitive_metadata(value: dict[str, Any]) -> dict[str, Any]:
    sensitive_keys = {
        "source_uri",
        "presigned_url",
        "signed_url",
        "raw_text",
        "extracted_text",
        "file_contents",
    }
    sanitized: dict[str, Any] = {}
    for key, item in value.items():
        if key in sensitive_keys:
            continue
        if isinstance(item, dict):
            sanitized[key] = _strip_sensitive_metadata(item)
        else:
            sanitized[key] = item
    return sanitized
