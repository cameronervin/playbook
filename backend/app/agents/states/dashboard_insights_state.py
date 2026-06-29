"""State and structured output schemas for dashboard insight generation."""

from __future__ import annotations

from typing import Any, Literal

from langchain.agents import AgentState
from pydantic import BaseModel, Field

DashboardInsightSeverity = Literal["low", "medium", "high"]


class DashboardInsightsStructuredResponse(BaseModel):
    """Validated dashboard insight output produced by the agent."""

    summary: str = Field(..., description="Short admin-facing insight summary.")
    headline_cards: list[dict[str, Any]] = Field(default_factory=list)
    topic_breakdown: list[dict[str, Any]] = Field(default_factory=list)
    unanswered_questions: list[dict[str, Any]] = Field(default_factory=list)
    risk_breakdown: list[dict[str, Any]] = Field(default_factory=list)
    recommended_attention_areas: list[str] = Field(default_factory=list)
    source_message_ids: list[str] = Field(
        default_factory=list,
        description="Anonymized source message IDs represented in the output.",
    )


class DashboardInsightsState(
    AgentState[DashboardInsightsStructuredResponse],
    total=False,
):
    """LangGraph state for one dashboard insight run.

    Keep fields JSON-safe so checkpoint payloads do not serialize sessions,
    repositories, or full ORM objects.
    """

    run_id: str
    organization_id: str
    window_start: str
    window_end: str
    source_filters: dict[str, Any]

    snapshot_context: str
    source_message_ids: list[str]

    summary: str
    headline_cards: list[dict[str, Any]]
    topic_breakdown: list[dict[str, Any]]
    unanswered_questions: list[dict[str, Any]]
    risk_breakdown: list[dict[str, Any]]
    recommended_attention_areas: list[str]

    completion_result: dict[str, Any]
