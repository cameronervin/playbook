"""Admin analytics service over anonymized athlete query data."""

from __future__ import annotations

import hmac
import re
from collections import Counter
from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings, get_settings
from app.core.exceptions import ValidationError
from app.models.identity import User
from app.repositories.analytics import (
    AdminAnalyticsRepository,
    AnalyticsQueryRecord,
)
from app.schemas.admin_analytics import (
    AdminAnalyticsQueryListResponse,
    AdminAnalyticsQueryResponse,
    AdminAnalyticsSnapshot,
    AdminAnalyticsSummaryResponse,
    LabelCount,
)

DEFAULT_ANALYTICS_WINDOW_DAYS = 7
WINDOW_RE = re.compile(r"^(?P<days>[1-9][0-9]*)d$")


class AdminAnalyticsService:
    """Build sanitized, organization-scoped admin analytics DTOs."""

    def __init__(
        self,
        session: AsyncSession,
        *,
        analytics_repo: AdminAnalyticsRepository | None = None,
        settings: Settings | None = None,
    ) -> None:
        self.session = session
        self.analytics_repo = analytics_repo or AdminAnalyticsRepository(session)
        self.settings = settings or get_settings()

    async def get_summary(
        self,
        *,
        actor: User,
        window: str | None = None,
        window_start: datetime | None = None,
        window_end: datetime | None = None,
        source_filters: dict[str, Any] | None = None,
    ) -> AdminAnalyticsSummaryResponse:
        """Return deterministic analytics summary for an admin dashboard window."""
        resolved_start, resolved_end = resolve_analytics_window(
            window=window,
            window_start=window_start,
            window_end=window_end,
            settings=self.settings,
        )
        records = await self._filtered_records(
            organization_id=actor.organization_id,
            window_start=resolved_start,
            window_end=resolved_end,
            source_filters=source_filters,
        )
        return _summary_from_records(
            records,
            window_start=resolved_start,
            window_end=resolved_end,
        )

    async def list_queries(
        self,
        *,
        actor: User,
        window: str | None = None,
        window_start: datetime | None = None,
        window_end: datetime | None = None,
        source_filters: dict[str, Any] | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> AdminAnalyticsQueryListResponse:
        """Return anonymized query rows for one admin analytics window."""
        resolved_start, resolved_end = resolve_analytics_window(
            window=window,
            window_start=window_start,
            window_end=window_end,
            settings=self.settings,
        )
        records = await self._filtered_records(
            organization_id=actor.organization_id,
            window_start=resolved_start,
            window_end=resolved_end,
            source_filters=source_filters,
        )
        page = records[offset : offset + limit]
        return AdminAnalyticsQueryListResponse(
            window_start=resolved_start,
            window_end=resolved_end,
            queries=[
                _query_response(
                    record,
                    organization_id=actor.organization_id,
                    settings=self.settings,
                )
                for record in page
            ],
        )

    async def build_snapshot(
        self,
        *,
        organization_id: UUID,
        window_start: datetime,
        window_end: datetime,
        source_filters: dict[str, Any] | None = None,
        max_queries: int | None = None,
    ) -> AdminAnalyticsSnapshot:
        """Return a bounded anonymized snapshot for dashboard insight generation."""
        records = await self._filtered_records(
            organization_id=organization_id,
            window_start=window_start,
            window_end=window_end,
            source_filters=source_filters,
        )
        resolved_max_queries = int(
            max_queries
            if max_queries is not None
            else getattr(self.settings, "DASHBOARD_INSIGHTS_MAX_QUERY_EXAMPLES", 50)
        )
        query_responses = [
            _query_response(
                record,
                organization_id=organization_id,
                settings=self.settings,
            )
            for record in records[:resolved_max_queries]
        ]
        return AdminAnalyticsSnapshot(
            summary=_summary_from_records(
                records,
                window_start=window_start,
                window_end=window_end,
            ),
            queries=query_responses,
            source_message_ids=[record.message_id for record in records],
        )

    async def _filtered_records(
        self,
        *,
        organization_id: UUID,
        window_start: datetime,
        window_end: datetime,
        source_filters: dict[str, Any] | None,
    ) -> list[AnalyticsQueryRecord]:
        records = await self.analytics_repo.list_query_records(
            organization_id=organization_id,
            window_start=window_start,
            window_end=window_end,
            limit=int(getattr(self.settings, "DASHBOARD_ANALYTICS_MAX_QUERY_ROWS", 5000)),
        )
        return _apply_source_filters(records, source_filters or {})


def resolve_analytics_window(
    *,
    window: str | None,
    window_start: datetime | None,
    window_end: datetime | None,
    settings: Settings | None = None,
) -> tuple[datetime, datetime]:
    """Resolve window shorthand or explicit start/end into aware UTC datetimes."""
    app_settings = settings or get_settings()
    if window_start is not None or window_end is not None:
        if window_start is None or window_end is None:
            raise ValidationError("window_start and window_end must be provided together")
        resolved_start = _aware_utc(window_start)
        resolved_end = _aware_utc(window_end)
    else:
        days = DEFAULT_ANALYTICS_WINDOW_DAYS
        if window:
            match = WINDOW_RE.match(window)
            if match is None:
                raise ValidationError("window must use a day shorthand such as 7d")
            days = int(match.group("days"))
        resolved_end = datetime.now(UTC)
        resolved_start = resolved_end - timedelta(days=days)

    if resolved_start >= resolved_end:
        raise ValidationError("window_start must be before window_end")
    max_days = int(getattr(app_settings, "DASHBOARD_INSIGHTS_MAX_WINDOW_DAYS", 30))
    if resolved_end - resolved_start > timedelta(days=max_days):
        raise ValidationError(f"Analytics window cannot exceed {max_days} days")
    return resolved_start, resolved_end


def format_snapshot_context(snapshot: AdminAnalyticsSnapshot) -> str:
    """Format sanitized snapshot text for the dashboard insight model."""
    summary = snapshot.summary
    lines = [
        "## Dashboard Analytics Snapshot",
        f"Window start: {summary.window_start.isoformat()}",
        f"Window end: {summary.window_end.isoformat()}",
        f"Query volume: {summary.query_volume}",
        f"Unanswered count: {summary.unanswered_count}",
        "Top topics: " + _format_label_counts(summary.top_topics),
        "Risk counts: " + _format_risk_counts(summary.risk_counts),
    ]
    if snapshot.queries:
        lines.append("## Anonymized Query Examples")
        for query in snapshot.queries:
            lines.append(
                "\n".join(
                    [
                        f"Message ID: {query.message_id}",
                        f"Anonymous user: {query.anonymous_user_key}",
                        f"Question: {query.text}",
                        "Topics: " + (", ".join(query.topic_labels) or "none"),
                        "Risks: " + (", ".join(query.risk_labels) or "none"),
                        f"Answer type: {query.answer_type or 'unknown'}",
                        f"Unanswered reason: {query.unanswered_reason or 'none'}",
                    ]
                )
            )
    return "\n\n".join(lines)


def _summary_from_records(
    records: list[AnalyticsQueryRecord],
    *,
    window_start: datetime,
    window_end: datetime,
) -> AdminAnalyticsSummaryResponse:
    topic_counts: Counter[str] = Counter()
    risk_counts: Counter[str] = Counter()
    for record in records:
        topic_counts.update(record.topic_labels)
        risk_counts.update(record.risk_labels)
    return AdminAnalyticsSummaryResponse(
        window_start=window_start,
        window_end=window_end,
        query_volume=len(records),
        top_topics=[
            LabelCount(label=label, count=count)
            for label, count in sorted(
                topic_counts.items(),
                key=lambda item: (-item[1], item[0]),
            )[:10]
        ],
        unanswered_count=sum(1 for record in records if record.unanswered_reason),
        risk_counts=dict(
            sorted(risk_counts.items(), key=lambda item: (-item[1], item[0]))
        ),
    )


def _query_response(
    record: AnalyticsQueryRecord,
    *,
    organization_id: UUID,
    settings: Settings,
) -> AdminAnalyticsQueryResponse:
    return AdminAnalyticsQueryResponse(
        message_id=record.message_id,
        anonymous_user_key=_anonymous_user_key(
            organization_id=organization_id,
            athlete_id=record.athlete_id,
            settings=settings,
        ),
        text=record.text,
        created_at=record.created_at,
        topic_labels=record.topic_labels,
        risk_labels=record.risk_labels,
        response_status=record.response_status,
        answer_type=record.answer_type,
        unanswered_reason=record.unanswered_reason,
    )


def _anonymous_user_key(
    *,
    organization_id: UUID,
    athlete_id: UUID,
    settings: Settings,
) -> str:
    message = f"{organization_id}:{athlete_id}".encode("utf-8")
    digest = hmac.digest(
        str(settings.SECRET_KEY).encode("utf-8"),
        message,
        "sha256",
    ).hex()[:16]
    return f"anon_{digest}"


def _apply_source_filters(
    records: list[AnalyticsQueryRecord],
    source_filters: dict[str, Any],
) -> list[AnalyticsQueryRecord]:
    topic_filter = _string_filter(source_filters.get("topic_labels"))
    risk_filter = _string_filter(source_filters.get("risk_labels"))
    status_filter = _string_filter(source_filters.get("message_statuses"))
    filtered: list[AnalyticsQueryRecord] = []
    for record in records:
        if topic_filter and not topic_filter.intersection(record.topic_labels):
            continue
        if risk_filter and not risk_filter.intersection(record.risk_labels):
            continue
        if status_filter and (record.response_status or "") not in status_filter:
            continue
        filtered.append(record)
    return filtered


def _string_filter(value: Any) -> set[str]:
    if value is None:
        return set()
    if isinstance(value, str):
        return {value} if value else set()
    if isinstance(value, list):
        return {str(item) for item in value if str(item)}
    return {str(value)}


def _aware_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)


def _format_label_counts(counts: list[LabelCount]) -> str:
    return ", ".join(f"{count.label}={count.count}" for count in counts) or "none"


def _format_risk_counts(counts: dict[str, int]) -> str:
    return ", ".join(f"{label}={count}" for label, count in counts.items()) or "none"
