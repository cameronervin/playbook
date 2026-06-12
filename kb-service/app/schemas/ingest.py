"""Pydantic schemas for POST /api/kb/ingest/url."""
from __future__ import annotations

import uuid

from pydantic import BaseModel, Field


class IngestURLRequest(BaseModel):
    document_id: uuid.UUID | None = Field(
        None,
        description="Caller-supplied UUID. When omitted, KB generates one.",
    )
    organization_id: uuid.UUID
    configuration_id: uuid.UUID
    url: str = Field(..., description="Presigned S3 URL for the document.")
    filename: str
    metadata: dict = Field(default_factory=dict)


class IngestURLResponse(BaseModel):
    task_id: str | None
    document_id: uuid.UUID
