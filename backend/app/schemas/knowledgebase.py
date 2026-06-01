"""Public knowledgebase schemas.

These schemas are the stable interface consumed by API routes, agent tools,
and chains. They are intentionally decoupled from any specific KB backend's
wire format.
"""
from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field

__all__ = [
    "RetrievedChunk",
    "KnowledgebaseResult",
    "KnowledgebaseHealthResponse",
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
