"""Pydantic schemas for document ingestion contract endpoints."""
from __future__ import annotations

import uuid
from datetime import date
from typing import Any

from pydantic import BaseModel, Field


class IngestDocumentRequest(BaseModel):
    """Start ingestion for an admin-uploaded Playbook KB document."""

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


class IngestDocumentResponse(BaseModel):
    """Response for a KB-service ingestion request."""

    kb_service_document_id: uuid.UUID
    playbook_document_id: uuid.UUID
    task_id: str | None
    status: str
