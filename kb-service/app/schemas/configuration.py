"""Pydantic schemas for /api/kb/configuration endpoints."""
from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, Field


class ConfigurationCreate(BaseModel):
    name: str = Field(..., max_length=255)
    collection_name: str = Field(..., max_length=255)
    parse_config: dict = Field(default_factory=dict)
    chunk_config: dict = Field(default_factory=dict)
    embed_config: dict = Field(default_factory=dict)
    vectorstore_config: dict = Field(default_factory=dict)


class ConfigurationResponse(BaseModel):
    id: uuid.UUID
    name: str
    collection_name: str
    version: int
    parse_config: dict
    chunk_config: dict
    embed_config: dict
    vectorstore_config: dict
    created_at: datetime
    updated_at: datetime

    # from_attributes lets us build this DTO directly from an ORM Configuration.
    model_config = {"from_attributes": True}
