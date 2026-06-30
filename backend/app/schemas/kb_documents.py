"""Knowledge-base document schemas."""

from __future__ import annotations

from datetime import date, datetime
from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.schemas.uploads import DirectUploadContract

KBDocumentStatus = Literal[
    "upload_pending",
    "uploaded",
    "processing",
    "ready",
    "failed",
]
KBSourceType = Literal["admin_upload", "conversation_file"]
KBCollectionIcon = Literal["shield", "plane", "book-open", "users", "database"]


class KBCollectionResponse(BaseModel):
    """Knowledge-base collection response."""

    id: UUID
    organization_id: UUID
    slug: str
    title: str
    description: str
    icon: KBCollectionIcon
    sort_order: int
    is_active: bool
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class KBCollectionCreateRequest(BaseModel):
    """Create a knowledge-base collection."""

    title: str = Field(min_length=1, max_length=120)
    description: str = Field(min_length=1, max_length=1000)
    icon: KBCollectionIcon = "database"

    model_config = ConfigDict(extra="forbid")

    @field_validator("title", "description")
    @classmethod
    def trim_required_text(cls, value: str) -> str:
        """Normalize required text inputs."""
        trimmed = value.strip()
        if not trimmed:
            raise ValueError("value must not be empty")
        return trimmed


class KBMetadataTagResponse(BaseModel):
    """Global KB metadata tag preset response."""

    id: UUID
    organization_id: UUID
    slug: str
    label: str
    sort_order: int
    is_active: bool
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class KBMetadataTagCreateRequest(BaseModel):
    """Create a global metadata tag preset."""

    label: str = Field(min_length=1, max_length=120)

    model_config = ConfigDict(extra="forbid")

    @field_validator("label")
    @classmethod
    def trim_label(cls, value: str) -> str:
        """Normalize tag labels."""
        trimmed = value.strip()
        if not trimmed:
            raise ValueError("label must not be empty")
        return trimmed


class KBMetadataTagUpdateRequest(BaseModel):
    """Update a global metadata tag preset."""

    label: str = Field(min_length=1, max_length=120)

    model_config = ConfigDict(extra="forbid")

    @field_validator("label")
    @classmethod
    def trim_label(cls, value: str) -> str:
        """Normalize tag labels."""
        trimmed = value.strip()
        if not trimmed:
            raise ValueError("label must not be empty")
        return trimmed


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
    collection_id: UUID | None = None
    tag_slugs: list[str] = Field(default_factory=list)
    visibility_policy: dict[str, Any]
    metadata_tags: dict[str, Any]
    source_date: date | None = None
    kb_service_document_id: UUID | None = None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class KBDocumentMetadataUpdateRequest(BaseModel):
    """Partial KB document metadata update."""

    tag_slugs: list[str] | None = None
    source_date: date | None = None

    model_config = ConfigDict(extra="forbid")


class KBDocumentUploadRequest(BaseModel):
    """Create a direct-upload request for an admin KB document."""

    filename: str = Field(min_length=1, max_length=500)
    content_type: str = Field(min_length=1, max_length=120)
    size_bytes: int = Field(gt=0)
    collection_id: UUID
    tag_slugs: list[str] = Field(default_factory=list)
    title: str | None = Field(default=None, max_length=500)
    source_date: date | None = None

    model_config = ConfigDict(extra="forbid")

    @field_validator("filename")
    @classmethod
    def trim_filename(cls, value: str) -> str:
        """Normalize path-bearing browser filenames to the leaf filename."""
        trimmed = value.replace("\\", "/").rsplit("/", 1)[-1].strip()
        if not trimmed:
            raise ValueError("filename must not be empty")
        return trimmed

    @field_validator("content_type")
    @classmethod
    def trim_content_type(cls, value: str) -> str:
        """Normalize accidental whitespace around content type values."""
        trimmed = value.strip()
        if not trimmed:
            raise ValueError("content_type must not be empty")
        return trimmed


class KBDocumentUploadRequestResponse(BaseModel):
    """Admin KB document plus direct browser upload contract."""

    document: KBDocumentResponse
    upload: DirectUploadContract


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
        "model_input",
        "model_inputs",
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
