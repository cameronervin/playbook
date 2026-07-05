"""Integration tests for admin analytics repositories."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

import pytest

from app.repositories.analytics import AdminAnalyticsRepository
from app.repositories.conversations import (
    ConversationMessageRepository,
    ConversationRepository,
)
from app.repositories.identity import OrganizationRepository, UserRepository


async def _seed_query(
    *,
    db_session,
    organization_id: UUID,
    athlete_id: UUID,
    question: str,
    created_at: datetime,
    assistant_status: str | None = "complete",
    answer_type: str | None = "grounded_answer",
    topic_labels: list[str] | None = None,
    risk_labels: list[str] | None = None,
    linked_to_user_message: bool = True,
) -> None:
    conversation = await ConversationRepository(db_session).create(
        organization_id=organization_id,
        athlete_id=athlete_id,
        title=question[:80],
    )
    message_repo = ConversationMessageRepository(db_session)
    user_message = await message_repo.create(
        conversation_id=conversation.id,
        role="user",
        content=question,
        created_at=created_at,
    )
    if assistant_status is None:
        return
    metadata_user_message_id = user_message.id if linked_to_user_message else uuid4()
    await message_repo.create(
        conversation_id=conversation.id,
        role="assistant",
        content="Assistant response",
        status=assistant_status,
        safety_outcome=answer_type,
        topic_labels=topic_labels or [],
        risk_labels=risk_labels or [],
        metadata={
            "user_message_id": str(metadata_user_message_id),
            "answer_type": answer_type,
        },
        created_at=created_at + timedelta(microseconds=1),
    )


@pytest.mark.asyncio
async def test_admin_analytics_repository_scopes_windows_pairs_and_pages(
    db_session,
) -> None:
    organization = await OrganizationRepository(db_session).create(
        name="Playbook Athletics",
        slug="playbook-analytics-repo",
    )
    other_org = await OrganizationRepository(db_session).create(
        name="Other Athletics",
        slug="other-analytics-repo",
    )
    user_repo = UserRepository(db_session)
    athlete = await user_repo.create(
        organization_id=organization.id,
        email="athlete@example.com",
        name="Jordan Athlete",
        auth_provider="google",
        provider_subject="athlete-subject",
        role="athlete",
    )
    other_athlete = await user_repo.create(
        organization_id=other_org.id,
        email="other@example.com",
        name="Other Athlete",
        auth_provider="google",
        provider_subject="other-athlete-subject",
        role="athlete",
    )
    window_start = datetime(2026, 6, 1, tzinfo=UTC)
    window_end = datetime(2026, 6, 8, tzinfo=UTC)
    await _seed_query(
        db_session=db_session,
        organization_id=organization.id,
        athlete_id=athlete.id,
        question="Start-boundary NIL question",
        created_at=window_start,
        topic_labels=["nil"],
        risk_labels=["compliance"],
    )
    await _seed_query(
        db_session=db_session,
        organization_id=organization.id,
        athlete_id=athlete.id,
        question="Declined recruiting question",
        created_at=datetime(2026, 6, 4, tzinfo=UTC),
        assistant_status="declined",
        answer_type="grounded_answer",
        topic_labels=["recruiting"],
        risk_labels=["recruiting"],
    )
    await _seed_query(
        db_session=db_session,
        organization_id=organization.id,
        athlete_id=athlete.id,
        question="Question without a matching assistant",
        created_at=datetime(2026, 6, 5, tzinfo=UTC),
        topic_labels=["nil"],
        risk_labels=["compliance"],
        linked_to_user_message=False,
    )
    await _seed_query(
        db_session=db_session,
        organization_id=organization.id,
        athlete_id=athlete.id,
        question="End-boundary excluded question",
        created_at=window_end,
        topic_labels=["nil"],
        risk_labels=["compliance"],
    )
    await _seed_query(
        db_session=db_session,
        organization_id=other_org.id,
        athlete_id=other_athlete.id,
        question="Other organization question",
        created_at=datetime(2026, 6, 6, tzinfo=UTC),
        topic_labels=["nil"],
        risk_labels=["compliance"],
    )

    repo = AdminAnalyticsRepository(db_session)
    records = await repo.list_query_records(
        organization_id=organization.id,
        window_start=window_start,
        window_end=window_end,
        limit=None,
    )
    paged_records = await repo.list_query_records(
        organization_id=organization.id,
        window_start=window_start,
        window_end=window_end,
        limit=1,
        offset=1,
    )

    assert [record.text for record in records] == [
        "Question without a matching assistant",
        "Declined recruiting question",
        "Start-boundary NIL question",
    ]
    assert records[0].response_status is None
    assert records[0].topic_labels == []
    assert records[0].unanswered_reason == "no_assistant_response"
    assert records[1].response_status == "declined"
    assert records[1].unanswered_reason == "declined"
    assert records[2].created_at == window_start
    assert [record.text for record in paged_records] == ["Declined recruiting question"]


@pytest.mark.asyncio
async def test_admin_analytics_repository_filters_before_limit(
    db_session,
) -> None:
    organization = await OrganizationRepository(db_session).create(
        name="Playbook Athletics",
        slug="playbook-analytics-repo-filters",
    )
    athlete = await UserRepository(db_session).create(
        organization_id=organization.id,
        email="athlete-filters@example.com",
        name="Jordan Athlete",
        auth_provider="google",
        provider_subject="athlete-filter-subject",
        role="athlete",
    )
    window_start = datetime(2026, 6, 1, tzinfo=UTC)
    window_end = datetime(2026, 6, 8, tzinfo=UTC)
    await _seed_query(
        db_session=db_session,
        organization_id=organization.id,
        athlete_id=athlete.id,
        question="Newer process question",
        created_at=datetime(2026, 6, 6, tzinfo=UTC),
        topic_labels=["process"],
        risk_labels=[],
    )
    await _seed_query(
        db_session=db_session,
        organization_id=organization.id,
        athlete_id=athlete.id,
        question="Failed NIL compliance question",
        created_at=datetime(2026, 6, 5, tzinfo=UTC),
        assistant_status="failed",
        topic_labels=["nil"],
        risk_labels=["compliance"],
    )
    await _seed_query(
        db_session=db_session,
        organization_id=organization.id,
        athlete_id=athlete.id,
        question="Older NIL compliance question",
        created_at=datetime(2026, 6, 4, tzinfo=UTC),
        topic_labels=["nil"],
        risk_labels=["compliance"],
    )
    await _seed_query(
        db_session=db_session,
        organization_id=organization.id,
        athlete_id=athlete.id,
        question="Older recruiting compliance question",
        created_at=datetime(2026, 6, 3, tzinfo=UTC),
        topic_labels=["recruiting"],
        risk_labels=["compliance"],
    )
    await _seed_query(
        db_session=db_session,
        organization_id=organization.id,
        athlete_id=athlete.id,
        question="Older NIL recruiting-risk question",
        created_at=datetime(2026, 6, 2, tzinfo=UTC),
        topic_labels=["nil"],
        risk_labels=["recruiting"],
    )

    records = await AdminAnalyticsRepository(db_session).list_query_records(
        organization_id=organization.id,
        window_start=window_start,
        window_end=window_end,
        source_filters={
            "topic_labels": ["nil", "recruiting"],
            "risk_labels": ["compliance"],
            "message_statuses": ["complete"],
        },
        limit=1,
    )

    assert [record.text for record in records] == ["Older NIL compliance question"]
