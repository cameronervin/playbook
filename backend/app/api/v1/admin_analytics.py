"""Admin analytics routes."""

from __future__ import annotations

from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, Depends, Query, Request
from fastapi.exceptions import RequestValidationError

from app.api.v1.dependencies import AdminAnalyticsServiceDep, AdminUserDep
from app.schemas.admin_analytics import (
    AdminAnalyticsQueryListResponse,
    AdminAnalyticsSummaryResponse,
)

router = APIRouter(prefix="/admin/analytics", tags=["Admin Analytics"])
QUERY_FILTER_ALLOWED_PARAMS = {
    "window",
    "window_start",
    "window_end",
    "topic_labels",
    "risk_labels",
    "limit",
    "offset",
}


def reject_unsupported_query_params(request: Request) -> None:
    """Reject unsupported analytics query-review parameters."""
    errors = [
        {
            "loc": ("query", param),
            "msg": "Unsupported query parameter.",
            "type": "value_error",
        }
        for param in sorted(set(request.query_params) - QUERY_FILTER_ALLOWED_PARAMS)
    ]
    if errors:
        raise RequestValidationError(errors)


def _normalized_source_filters(
    *,
    topic_labels: list[str] | None,
    risk_labels: list[str] | None,
) -> dict[str, list[str]]:
    source_filters: dict[str, list[str]] = {}
    normalized_topics = _normalized_filter_values(topic_labels)
    normalized_risks = _normalized_filter_values(risk_labels)
    if normalized_topics:
        source_filters["topic_labels"] = normalized_topics
    if normalized_risks:
        source_filters["risk_labels"] = normalized_risks
    return source_filters


def _normalized_filter_values(values: list[str] | None) -> list[str]:
    normalized: list[str] = []
    seen: set[str] = set()
    for value in values or []:
        label = value.strip()
        if not label or label in seen:
            continue
        normalized.append(label)
        seen.add(label)
    return normalized


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


@router.get(
    "/queries",
    response_model=AdminAnalyticsQueryListResponse,
    dependencies=[Depends(reject_unsupported_query_params)],
)
async def list_queries(
    actor: AdminUserDep,
    service: AdminAnalyticsServiceDep,
    window: Annotated[str | None, Query(pattern=r"^[1-9][0-9]*d$")] = None,
    window_start: datetime | None = None,
    window_end: datetime | None = None,
    topic_labels: Annotated[list[str] | None, Query()] = None,
    risk_labels: Annotated[list[str] | None, Query()] = None,
    limit: Annotated[int, Query(ge=1, le=500)] = 100,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> AdminAnalyticsQueryListResponse:
    """Return anonymized athlete query text for admin review."""
    source_filters = _normalized_source_filters(
        topic_labels=topic_labels,
        risk_labels=risk_labels,
    )
    return await service.list_queries(
        actor=actor,
        window=window,
        window_start=window_start,
        window_end=window_end,
        source_filters=source_filters,
        limit=limit,
        offset=offset,
    )
