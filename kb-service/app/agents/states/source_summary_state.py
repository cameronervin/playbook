"""Structured output schema for source summaries."""
from __future__ import annotations

from pydantic import BaseModel, Field


class SourceSummaryStructuredResponse(BaseModel):
    """Validated source-summary output from the summary agent."""

    summary: str = Field(
        ...,
        min_length=1,
        description="One- or two-sentence source orientation summary.",
    )
