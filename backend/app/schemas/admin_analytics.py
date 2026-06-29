"""Admin analytics and dashboard insight schemas."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

DashboardInsightRunStatus = Literal["pending", "processing", "completed", "failed"]
DashboardInsightTriggerType = Literal["nightly", "manual"]


class LabelCount(BaseModel):
    """Count for one analytics label."""

    label: str
    count: int


class AdminAnalyticsSummaryResponse(BaseModel):
    """Admin dashboard analytics summary."""

    window_start: datetime
    window_end: datetime
    query_volume: int
    top_topics: list[LabelCount] = Field(default_factory=list)
    unanswered_count: int = 0
    risk_counts: dict[str, int] = Field(default_factory=dict)


class AdminAnalyticsQueryResponse(BaseModel):
    """An anonymized athlete query row for admin review."""

    message_id: UUID
    anonymous_user_key: str
    text: str
    created_at: datetime
    topic_labels: list[str] = Field(default_factory=list)
    risk_labels: list[str] = Field(default_factory=list)
    response_status: str | None = None
    answer_type: str | None = None
    unanswered_reason: str | None = None


class AdminAnalyticsQueryListResponse(BaseModel):
    """Paginated anonymized query response."""

    window_start: datetime
    window_end: datetime
    queries: list[AdminAnalyticsQueryResponse]


class AdminAnalyticsSnapshot(BaseModel):
    """Sanitized analytics snapshot passed to the dashboard insights agent."""

    summary: AdminAnalyticsSummaryResponse
    queries: list[AdminAnalyticsQueryResponse] = Field(default_factory=list)
    source_message_ids: list[UUID] = Field(default_factory=list)


class DashboardInsightResponse(BaseModel):
    """Generated dashboard insight output."""

    id: UUID
    run_id: UUID
    summary: str
    headline_cards: list[dict[str, Any]] = Field(default_factory=list)
    topic_breakdown: list[dict[str, Any]] = Field(default_factory=list)
    unanswered_questions: list[dict[str, Any]] = Field(default_factory=list)
    risk_breakdown: list[dict[str, Any]] = Field(default_factory=list)
    recommended_attention_areas: list[str] = Field(default_factory=list)
    source_message_ids: list[UUID] = Field(default_factory=list)
    generated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class DashboardInsightRunCreateRequest(BaseModel):
    """Create a manual dashboard insight run."""

    window_start: datetime
    window_end: datetime
    source_filters: dict[str, Any] = Field(default_factory=dict)


class DashboardInsightRunStartResponse(BaseModel):
    """Response returned after enqueueing a dashboard insight run."""

    run_id: UUID
    status: DashboardInsightRunStatus


class DashboardInsightRunResponse(BaseModel):
    """Dashboard insight run lifecycle response."""

    id: UUID
    organization_id: UUID
    requested_by: UUID | None = None
    trigger_type: DashboardInsightTriggerType
    status: DashboardInsightRunStatus
    window_start: datetime
    window_end: datetime
    source_filters: dict[str, Any] = Field(default_factory=dict)
    error_message: str | None = None
    created_at: datetime
    updated_at: datetime
    output: DashboardInsightResponse | None = None

    model_config = ConfigDict(from_attributes=True)
