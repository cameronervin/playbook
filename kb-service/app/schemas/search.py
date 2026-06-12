"""Pydantic schemas for POST /api/kb/embed/search."""
from __future__ import annotations

import uuid
from typing import Any

from pydantic import BaseModel, Field

from app.core.config import settings


class SearchRequest(BaseModel):
    query: str
    organization_id: uuid.UUID
    configuration_id: uuid.UUID
    max_docs: int = Field(settings.KB_SEARCH_MAX_DOCS, ge=1, le=100)
    score_threshold: float = Field(settings.KB_SEARCH_SCORE_THRESHOLD, ge=0.0, le=1.0)
    metadata_filter: dict[str, Any] | None = None


class SearchChunk(BaseModel):
    document_id: uuid.UUID
    kb_service_document_id: uuid.UUID
    chunk_id: uuid.UUID | None = None
    chunk_index: int | None = None
    text: str
    score: float
    metadata: dict[str, Any] = Field(default_factory=dict)


class SearchResponse(BaseModel):
    chunks: list[SearchChunk]
    query: str
    total: int
