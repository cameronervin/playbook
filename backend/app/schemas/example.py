"""Pydantic DTOs for the Example entity."""
from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class ExampleCreate(BaseModel):
    """Request body for creating an Example."""

    name: str = Field(..., min_length=1, max_length=255)
    status: str = Field(default="active", max_length=50)


class ExampleUpdate(BaseModel):
    """Request body for updating an Example. All fields optional."""

    name: str | None = Field(default=None, min_length=1, max_length=255)
    status: str | None = Field(default=None, max_length=50)


class ExampleResponse(BaseModel):
    """Response DTO for an Example. Built from the ORM model via from_attributes."""

    id: UUID
    name: str
    status: str
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)
