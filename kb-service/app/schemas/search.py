"""Pydantic schemas for POST /api/kb/search."""
from __future__ import annotations

import uuid
from typing import Any, Literal

from pydantic import BaseModel, Field, field_validator, model_validator

from app.core.config import settings

KBSourceType = Literal["admin_upload", "conversation_file"]


class SearchRequest(BaseModel):
    query: str
    organization_id: uuid.UUID
    visibility_context: dict[str, Any] = Field(default_factory=dict)
    source_types: list[KBSourceType] = Field(
        default_factory=lambda: ["admin_upload"],
    )
    conversation_id: uuid.UUID | None = None
    file_ids: list[uuid.UUID] = Field(default_factory=list)
    limit: int = Field(settings.KB_SEARCH_MAX_DOCS, ge=1, le=100)
    score_threshold: float = Field(settings.KB_SEARCH_SCORE_THRESHOLD, ge=0.0, le=1.0)

    @field_validator("source_types")
    @classmethod
    def validate_source_types(
        cls,
        value: list[KBSourceType],
    ) -> list[KBSourceType]:
        if not value:
            raise ValueError("source_types must contain at least one source type")
        if len(set(value)) != len(value):
            raise ValueError("source_types must not contain duplicate values")
        return value

    @model_validator(mode="after")
    def validate_private_scope(self) -> "SearchRequest":
        includes_private = "conversation_file" in self.source_types
        if includes_private and self.conversation_id is None:
            raise ValueError(
                "conversation_id is required when source_types includes "
                "conversation_file"
            )
        if self.file_ids and not includes_private:
            raise ValueError(
                "file_ids may only be used when source_types includes "
                "conversation_file"
            )
        return self


class SearchResult(BaseModel):
    document_id: uuid.UUID
    kb_service_document_id: uuid.UUID
    chunk_id: uuid.UUID | None = None
    chunk_index: int | None = None
    text: str
    score: float
    metadata: dict[str, Any] = Field(default_factory=dict)


class SearchResponse(BaseModel):
    results: list[SearchResult]
    query: str
    total: int
