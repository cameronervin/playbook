"""Unit tests for admin analytics service behavior."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any
from uuid import UUID, uuid4

import pytest

from app.core.exceptions import ValidationError
from app.models.identity import User
from app.repositories.analytics import AnalyticsQueryRecord
from app.services.admin_analytics import AdminAnalyticsService, resolve_analytics_window


class FakeAnalyticsRepository:
    """Small fake matching the repository method used by the service."""

    def __init__(self, records: list[AnalyticsQueryRecord]) -> None:
        self.records = records
        self.calls: list[dict[str, Any]] = []

    async def list_query_records(
        self,
        *,
        organization_id: UUID,
        window_start: datetime,
        window_end: datetime,
        source_filters: dict[str, Any] | None = None,
        limit: int | None = 5000,
        offset: int = 0,
    ) -> list[AnalyticsQueryRecord]:
        self.calls.append(
            {
                "organization_id": organization_id,
                "window_start": window_start,
                "window_end": window_end,
                "source_filters": source_filters,
                "limit": limit,
                "offset": offset,
            }
        )
        records = _apply_fake_filters(self.records, source_filters or {})
        if offset:
            records = records[offset:]
        if limit is not None:
            records = records[:limit]
        return records


def _actor(organization_id: UUID) -> User:
    return User(
        organization_id=organization_id,
        email="admin@example.com",
        name="Admin User",
        auth_provider="google",
        provider_subject="admin-subject",
        role="admin",
    )


def _record(
    *,
    text: str,
    created_at: datetime,
    athlete_id: UUID | None = None,
    response_status: str | None = "complete",
    answer_type: str | None = "grounded_answer",
    topic_labels: list[str] | None = None,
    risk_labels: list[str] | None = None,
    unanswered_reason: str | None = None,
) -> AnalyticsQueryRecord:
    return AnalyticsQueryRecord(
        message_id=uuid4(),
        conversation_id=uuid4(),
        athlete_id=athlete_id or uuid4(),
        text=text,
        created_at=created_at,
        response_status=response_status,
        answer_type=answer_type,
        topic_labels=topic_labels or [],
        risk_labels=risk_labels or [],
        unanswered_reason=unanswered_reason,
    )


def _apply_fake_filters(
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


@pytest.mark.asyncio
async def test_get_summary_counts_topics_risks_and_unanswered_without_cap(
    test_settings,
) -> None:
    organization_id = uuid4()
    records = [
        _record(
            text="NIL disclosure",
            created_at=datetime(2026, 6, 4, tzinfo=UTC),
            topic_labels=["nil"],
            risk_labels=["compliance"],
        ),
        _record(
            text="Recruiting text",
            created_at=datetime(2026, 6, 3, tzinfo=UTC),
            answer_type="unsupported",
            topic_labels=["recruiting"],
            risk_labels=["recruiting"],
            unanswered_reason="unsupported",
        ),
        _record(
            text="Another NIL question",
            created_at=datetime(2026, 6, 2, tzinfo=UTC),
            topic_labels=["nil"],
            risk_labels=["compliance"],
        ),
    ]
    repo = FakeAnalyticsRepository(records)
    service = AdminAnalyticsService(
        None,  # type: ignore[arg-type]
        analytics_repo=repo,  # type: ignore[arg-type]
        settings=test_settings,
    )

    summary = await service.get_summary(
        actor=_actor(organization_id),
        window_start=datetime(2026, 6, 1, tzinfo=UTC),
        window_end=datetime(2026, 6, 8, tzinfo=UTC),
    )

    assert summary.query_volume == 3
    assert [count.model_dump() for count in summary.top_topics] == [
        {"label": "nil", "count": 2},
        {"label": "recruiting", "count": 1},
    ]
    assert summary.risk_counts == {"compliance": 2, "recruiting": 1}
    assert summary.unanswered_count == 1
    assert [point.model_dump() for point in summary.volume_series] == [
        {"date": "2026-06-01", "total": 0, "unanswered": 0},
        {"date": "2026-06-02", "total": 1, "unanswered": 0},
        {"date": "2026-06-03", "total": 1, "unanswered": 1},
        {"date": "2026-06-04", "total": 1, "unanswered": 0},
        {"date": "2026-06-05", "total": 0, "unanswered": 0},
        {"date": "2026-06-06", "total": 0, "unanswered": 0},
        {"date": "2026-06-07", "total": 0, "unanswered": 0},
    ]
    assert repo.calls[0]["limit"] is None


@pytest.mark.asyncio
async def test_list_queries_filters_pages_and_uses_stable_anonymous_keys(
    test_settings,
) -> None:
    organization_id = uuid4()
    athlete_id = uuid4()
    matching_newer = _record(
        text="Newer NIL compliance question",
        created_at=datetime(2026, 6, 5, tzinfo=UTC),
        athlete_id=athlete_id,
        topic_labels=["nil"],
        risk_labels=["compliance"],
    )
    matching_older = _record(
        text="Older recruiting compliance question",
        created_at=datetime(2026, 6, 4, tzinfo=UTC),
        athlete_id=athlete_id,
        topic_labels=["recruiting"],
        risk_labels=["compliance"],
    )
    repo = FakeAnalyticsRepository(
        [
            matching_newer,
            matching_older,
            _record(
                text="Nonmatching process question",
                created_at=datetime(2026, 6, 3, tzinfo=UTC),
                topic_labels=["process"],
                risk_labels=[],
            ),
        ]
    )
    service = AdminAnalyticsService(
        None,  # type: ignore[arg-type]
        analytics_repo=repo,  # type: ignore[arg-type]
        settings=test_settings,
    )

    first_response = await service.list_queries(
        actor=_actor(organization_id),
        window_start=datetime(2026, 6, 1, tzinfo=UTC),
        window_end=datetime(2026, 6, 8, tzinfo=UTC),
        source_filters={
            "topic_labels": ["nil", "recruiting"],
            "risk_labels": ["compliance"],
            "message_statuses": ["complete"],
        },
        limit=1,
        offset=1,
    )
    second_response = await service.list_queries(
        actor=_actor(organization_id),
        window_start=datetime(2026, 6, 1, tzinfo=UTC),
        window_end=datetime(2026, 6, 8, tzinfo=UTC),
        source_filters={
            "topic_labels": ["nil", "recruiting"],
            "risk_labels": ["compliance"],
            "message_statuses": ["complete"],
        },
        limit=1,
        offset=1,
    )

    assert [query.text for query in first_response.queries] == [
        "Older recruiting compliance question"
    ]
    assert first_response.queries[0].anonymous_user_key.startswith("anon_")
    assert (
        first_response.queries[0].anonymous_user_key
        == second_response.queries[0].anonymous_user_key
    )
    assert str(athlete_id) not in first_response.model_dump_json()
    assert str(matching_older.conversation_id) not in first_response.model_dump_json()
    assert repo.calls[0]["limit"] == 1
    assert repo.calls[0]["offset"] == 1


@pytest.mark.asyncio
async def test_build_snapshot_limits_examples_but_keeps_full_summary_and_sources(
    test_settings,
) -> None:
    organization_id = uuid4()
    records = [
        _record(
            text=f"Question {index}",
            created_at=datetime(2026, 6, index, tzinfo=UTC),
            topic_labels=["nil"],
            risk_labels=["compliance"],
        )
        for index in range(1, 4)
    ]
    service = AdminAnalyticsService(
        None,  # type: ignore[arg-type]
        analytics_repo=FakeAnalyticsRepository(records),  # type: ignore[arg-type]
        settings=test_settings,
    )

    snapshot = await service.build_snapshot(
        organization_id=organization_id,
        window_start=datetime(2026, 6, 1, tzinfo=UTC),
        window_end=datetime(2026, 6, 8, tzinfo=UTC),
        max_queries=2,
    )

    assert snapshot.summary.query_volume == 3
    assert [query.text for query in snapshot.queries] == ["Question 1", "Question 2"]
    assert snapshot.source_message_ids == [record.message_id for record in records]


def test_resolve_analytics_window_accepts_explicit_naive_datetimes(test_settings) -> None:
    window_start, window_end = resolve_analytics_window(
        window=None,
        window_start=datetime(2026, 6, 1),  # noqa: DTZ001 - verifies naive input normalization
        window_end=datetime(2026, 6, 8),  # noqa: DTZ001 - verifies naive input normalization
        settings=test_settings,
    )

    assert window_start == datetime(2026, 6, 1, tzinfo=UTC)
    assert window_end == datetime(2026, 6, 8, tzinfo=UTC)


@pytest.mark.parametrize(
    ("window", "window_start", "window_end", "expected_message"),
    [
        ("bad", None, None, "window must use a day shorthand"),
        (
            None,
            datetime(2026, 6, 1, tzinfo=UTC),
            None,
            "window_start and window_end must be provided together",
        ),
        (
            None,
            datetime(2026, 6, 8, tzinfo=UTC),
            datetime(2026, 6, 1, tzinfo=UTC),
            "window_start must be before window_end",
        ),
        (
            None,
            datetime(2026, 1, 1, tzinfo=UTC),
            datetime(2026, 6, 8, tzinfo=UTC),
            "Analytics window cannot exceed",
        ),
    ],
)
def test_resolve_analytics_window_rejects_invalid_windows(
    test_settings,
    window: str | None,
    window_start: datetime | None,
    window_end: datetime | None,
    expected_message: str,
) -> None:
    with pytest.raises(ValidationError, match=expected_message):
        resolve_analytics_window(
            window=window,
            window_start=window_start,
            window_end=window_end,
            settings=test_settings,
        )
