"""Public knowledgebase schemas.

These schemas are the stable interface consumed by API routes, agent tools,
and chains. They are intentionally decoupled from any specific KB backend's
wire format.
"""
from __future__ import annotations

from datetime import date
from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, Field

__all__ = [
    "RetrievedChunk",
    "KnowledgebaseResult",
    "KnowledgebaseHealthResponse",
    "KBDocumentIngestRequest",
    "KBDocumentIngestResponse",
    "KBDocumentStatusResponse",
]


class RetrievedChunk(BaseModel):
    """A single retrieved chunk with source metadata."""

    text: str
    metadata: dict[str, Any] = Field(default_factory=dict)
    similarity_score: float | None = None


class KnowledgebaseResult(BaseModel):
    """Result from a KB retrieval operation."""

    query: str = Field(..., description="Original query sent to the knowledge base")
    context: str = Field(..., description="Assembled context string for LLM injection")
    sources: list[RetrievedChunk] = Field(default_factory=list)
    confidence: float | None = Field(None, ge=0.0, le=1.0)
    zero_hit: bool = Field(default=False, description="True when no results exceeded the score threshold")
    latency_ms: int = Field(..., description="Round-trip latency in milliseconds")


class KnowledgebaseHealthResponse(BaseModel):
    """Health check response for the knowledgebase endpoint."""

    status: Literal["healthy", "degraded", "unavailable"]
    provider_reachable: bool
    configuration_resolved: bool
    latency_ms: int


class KBDocumentIngestRequest(BaseModel):
    """Semantic backend-to-KB-service document ingest request."""

    playbook_document_id: UUID
    source_uri: str
    filename: str
    content_type: str
    size_bytes: int
    source_title: str
    source_date: date | None = None
    is_official: bool = False
    priority: int = 0
    visibility_policy: dict[str, Any] = Field(
        default_factory=lambda: {"scope": "all_athletes"}
    )
    metadata_tags: dict[str, Any] = Field(default_factory=dict)


class KBDocumentIngestResponse(BaseModel):
    """Semantic backend-to-KB-service document ingest response."""

    kb_service_document_id: UUID
    playbook_document_id: UUID
    task_id: str | None = None
    status: str = "pending"


class KBDocumentStatusResponse(BaseModel):
    """KB-service task/document status response."""

    document_id: UUID | None = None
    task_id: str | None = None
    status: str | None = None
    error_message: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)
