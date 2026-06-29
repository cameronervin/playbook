"""Admin analytics routes."""

from __future__ import annotations

from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, Query

from app.api.v1.dependencies import AdminAnalyticsServiceDep, AdminUserDep
from app.schemas.admin_analytics import (
    AdminAnalyticsQueryListResponse,
    AdminAnalyticsSummaryResponse,
)

router = APIRouter(prefix="/admin/analytics", tags=["Admin Analytics"])


@router.get("/summary", response_model=AdminAnalyticsSummaryResponse)
async def get_summary(
    actor: AdminUserDep,
    service: AdminAnalyticsServiceDep,
    window: Annotated[str | None, Query(pattern=r"^[1-9][0-9]*d$")] = None,
    window_start: datetime | None = None,
    window_end: datetime | None = None,
) -> AdminAnalyticsSummaryResponse:
    """Return anonymized query analytics summary for the current organization."""
    return await service.get_summary(
        actor=actor,
        window=window,
        window_start=window_start,
        window_end=window_end,
    )


@router.get("/queries", response_model=AdminAnalyticsQueryListResponse)
async def list_queries(
    actor: AdminUserDep,
    service: AdminAnalyticsServiceDep,
    window: Annotated[str | None, Query(pattern=r"^[1-9][0-9]*d$")] = None,
    window_start: datetime | None = None,
    window_end: datetime | None = None,
    topic_label: str | None = None,
    risk_label: str | None = None,
    limit: Annotated[int, Query(ge=1, le=500)] = 100,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> AdminAnalyticsQueryListResponse:
    """Return anonymized athlete query text for admin review."""
    source_filters: dict[str, list[str]] = {}
    if topic_label:
        source_filters["topic_labels"] = [topic_label]
    if risk_label:
        source_filters["risk_labels"] = [risk_label]
    return await service.list_queries(
        actor=actor,
        window=window,
        window_start=window_start,
        window_end=window_end,
        source_filters=source_filters,
        limit=limit,
        offset=offset,
    )
