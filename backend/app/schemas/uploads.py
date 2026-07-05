"""Shared schemas for direct-upload request contracts."""

from __future__ import annotations

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field


class DirectUploadContract(BaseModel):
    """Browser storage upload contract returned after backend authorization."""

    upload_request_id: UUID
    method: Literal["POST"] = "POST"
    url: str
    fields: dict[str, str] = Field(default_factory=dict)
    expires_at: datetime


class UploadCompleteRequest(BaseModel):
    """Request body for completing a direct upload after storage POST succeeds."""

    upload_request_id: UUID
