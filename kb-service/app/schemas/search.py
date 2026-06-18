"""Pydantic schemas for POST /api/kb/search."""
from __future__ import annotations

import uuid
from typing import Any, Literal

from pydantic import BaseModel, Field, field_validator, model_validator

from app.core.config import settings

KBSourceType = Literal["admin_upload", "conversation_file"]


class SearchRequest(BaseModel):
    query: str = Field(description="Natural-language retrieval query.")
    organization_id: uuid.UUID = Field(
        description="Trusted Playbook organization scope supplied by the backend."
    )
    visibility_context: dict[str, Any] = Field(
        default_factory=dict,
        description=(
            "Trusted backend visibility context. Athlete shared-KB search uses "
            'visibility_policy.scope="all_athletes"; private conversation-file '
            "search uses conversation-scoped metadata."
        ),
    )
    source_types: list[KBSourceType] = Field(
        default_factory=lambda: ["admin_upload"],
        description=(
            'Source scopes to search. Defaults to ["admin_upload"]. '
            '"conversation_file" may be used only by trusted backend callers '
            "and requires conversation_id; browser callers must not choose "
            "source types directly."
        ),
    )
    conversation_id: uuid.UUID | None = Field(
        default=None,
        description=(
            "Trusted private conversation scope. Required when source_types "
            'includes "conversation_file".'
        ),
    )
    file_ids: list[uuid.UUID] = Field(
        default_factory=list,
        description=(
            "Optional trusted conversation-file IDs to narrow private retrieval. "
            'Only valid with source_types including "conversation_file".'
        ),
    )
    limit: int = Field(
        settings.KB_SEARCH_MAX_DOCS,
        ge=1,
        le=100,
        description="Maximum number of final retrieval results to return.",
    )
    score_threshold: float = Field(
        settings.KB_SEARCH_SCORE_THRESHOLD,
        ge=0.0,
        le=1.0,
        description=(
            "Minimum final retrieval score to include. Current semantic search "
            "maps this to pgvector cosine similarity; future hybrid/rerank "
            "scores remain exposed through the final score contract."
        ),
    )

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
    document_id: uuid.UUID = Field(
        description=(
            "External Playbook source identifier: kb_documents.id for "
            "admin uploads or conversation_files.id for private files."
        )
    )
    kb_service_document_id: uuid.UUID = Field(
        description="KB-service internal document identifier for status/debug linkage."
    )
    chunk_id: uuid.UUID | None = Field(
        default=None,
        description="Stable chunk identifier used for citation persistence.",
    )
    chunk_index: int | None = Field(
        default=None,
        description="Zero-based chunk index within the KB-service document.",
    )
    text: str = Field(description="Retrieved chunk text.")
    score: float = Field(
        description=(
            "Final caller-facing retrieval score. Current runtime behavior is "
            "semantic cosine similarity (1 - pgvector cosine distance); future "
            "semantic, lexical, hybrid, and rerank diagnostics belong in metadata."
        )
    )
    metadata: dict[str, Any] = Field(
        default_factory=dict,
        description=(
            "Citation/source metadata. Reserved future ranking diagnostics include "
            "semantic_score, semantic_rank, lexical_score, lexical_rank, "
            "hybrid_score, rerank_score, and ranking_strategy."
        ),
    )


class SearchResponse(BaseModel):
    results: list[SearchResult]
    query: str
    total: int
