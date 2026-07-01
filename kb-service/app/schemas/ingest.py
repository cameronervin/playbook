"""Pydantic schemas for document ingestion contract endpoints."""
from __future__ import annotations

import uuid
from datetime import date
from typing import Annotated, Any, Literal

from pydantic import BaseModel, Field

KBSourceType = Literal["admin_upload", "conversation_file"]


class IngestDocumentRequest(BaseModel):
    """Start ingestion for an admin-uploaded Playbook KB document."""

    source_type: Literal["admin_upload"] = "admin_upload"
    organization_id: uuid.UUID
    playbook_document_id: uuid.UUID
    configuration_id: uuid.UUID
    source_uri: str = Field(..., description="Signed or presigned source URL.")
    filename: str
    content_type: str
    size_bytes: int = Field(..., ge=0)
    source_title: str
    source_date: date | None = None
    is_official: bool = True
    priority: int = 0
    visibility_policy: dict[str, Any] = Field(
        default_factory=lambda: {"scope": "all_athletes"}
    )
    metadata_tags: dict[str, Any] = Field(default_factory=dict)
    status_webhook_url: str | None = None


class IngestConversationFileRequest(BaseModel):
    """Start ingestion for a conversation-scoped Playbook file."""

    source_type: Literal["conversation_file"] = "conversation_file"
    organization_id: uuid.UUID
    conversation_id: uuid.UUID
    conversation_file_id: uuid.UUID
    configuration_id: uuid.UUID
    source_uri: str = Field(..., description="Signed or presigned source URL.")
    filename: str
    content_type: str
    size_bytes: int = Field(..., ge=0)
    source_title: str
    visibility_policy: dict[str, Any] = Field(
        default_factory=lambda: {"scope": "conversation"}
    )
    metadata_tags: dict[str, Any] = Field(default_factory=dict)
    status_webhook_url: str | None = None


IngestSourceRequest = Annotated[
    IngestDocumentRequest | IngestConversationFileRequest,
    Field(discriminator="source_type"),
]


class IngestDocumentResponse(BaseModel):
    """Response for a KB-service ingestion request."""

    kb_service_document_id: uuid.UUID
    source_type: KBSourceType = "admin_upload"
    playbook_document_id: uuid.UUID | None = None
    conversation_id: uuid.UUID | None = None
    conversation_file_id: uuid.UUID | None = None
    task_id: str | None
    status: str


class DocumentMetadataRefreshRequest(BaseModel):
    """Refresh metadata for an already-ingested KB-service document."""

    source_date: date | None = None
    is_official: bool = True
    priority: int = 0
    visibility_policy: dict[str, Any] = Field(
        default_factory=lambda: {"scope": "all_athletes"}
    )
    metadata_tags: dict[str, Any] = Field(default_factory=dict)


class DocumentMetadataRefreshResponse(BaseModel):
    """Response for a KB-service metadata refresh request."""

    kb_service_document_id: uuid.UUID
    source_type: KBSourceType = "admin_upload"
    playbook_document_id: uuid.UUID | None = None
    updated_embedding_count: int = 0
    metadata: dict[str, Any] = Field(default_factory=dict)
