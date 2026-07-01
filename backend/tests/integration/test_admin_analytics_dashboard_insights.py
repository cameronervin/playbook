"""Integration tests for admin analytics and dashboard insight APIs."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import select

from app.models.analytics import DashboardInsightRun
from app.models.audit import AuditLog
from app.repositories.analytics import (
    DashboardInsightRepository,
    DashboardInsightRunRepository,
)
from app.repositories.conversations import (
    ConversationMessageRepository,
    ConversationRepository,
)
from app.repositories.identity import OrganizationRepository, UserRepository
from app.services.dashboard_insights import DashboardInsightService
from app.workers import dispatcher as worker_dispatcher


async def _seed_turn(
    *,
    db_session,
    organization_id,
    athlete_id,
    question: str,
    created_at: datetime,
    assistant_status: str = "complete",
    answer_type: str = "grounded_answer",
    topic_labels: list[str] | None = None,
    risk_labels: list[str] | None = None,
):
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
    assistant_message = await message_repo.create(
        conversation_id=conversation.id,
        role="assistant",
        content="Assistant response",
        status=assistant_status,
        safety_outcome=answer_type,
        topic_labels=topic_labels or [],
        risk_labels=risk_labels or [],
        metadata={
            "user_message_id": str(user_message.id),
            "answer_type": answer_type,
        },
        created_at=created_at + timedelta(microseconds=1),
    )
    return user_message, assistant_message


@pytest.mark.asyncio
async def test_admin_analytics_summary_and_queries_anonymize_athlete_identity(
    route_client,
    db_session,
) -> None:
    organization = await OrganizationRepository(db_session).create(
        name="Playbook Athletics",
        slug="playbook",
    )
    other_org = await OrganizationRepository(db_session).create(
        name="Other Athletics",
        slug="other",
    )
    user_repo = UserRepository(db_session)
    admin = await user_repo.create(
        organization_id=organization.id,
        email="admin@example.com",
        name="Admin User",
        auth_provider="google",
        provider_subject="admin-subject",
        role="admin",
    )
    athlete = await user_repo.create(
        organization_id=organization.id,
        email="jordan@example.com",
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
    await _seed_turn(
        db_session=db_session,
        organization_id=organization.id,
        athlete_id=athlete.id,
        question="When do I disclose an NIL deal?",
        created_at=datetime(2026, 6, 2, tzinfo=UTC),
        topic_labels=["nil"],
        risk_labels=["compliance"],
    )
    await _seed_turn(
        db_session=db_session,
        organization_id=organization.id,
        athlete_id=athlete.id,
        question="Can recruiting staff text this prospect?",
        created_at=datetime(2026, 6, 3, tzinfo=UTC),
        answer_type="unsupported",
        topic_labels=["recruiting"],
        risk_labels=["recruiting"],
    )
    await _seed_turn(
        db_session=db_session,
        organization_id=other_org.id,
        athlete_id=other_athlete.id,
        question="Other org question",
        created_at=datetime(2026, 6, 4, tzinfo=UTC),
        topic_labels=["nil"],
    )
    route_client.authenticate_as(admin)

    summary_response = await route_client.client.get(
        "/api/v1/admin/analytics/summary",
        params={
            "window_start": window_start.isoformat(),
            "window_end": window_end.isoformat(),
        },
    )
    queries_response = await route_client.client.get(
        "/api/v1/admin/analytics/queries",
        params={
            "window_start": window_start.isoformat(),
            "window_end": window_end.isoformat(),
        },
    )

    assert summary_response.status_code == 200
    summary = summary_response.json()
    assert summary["query_volume"] == 2
    assert summary["top_topics"] == [
        {"label": "nil", "count": 1},
        {"label": "recruiting", "count": 1},
    ]
    assert summary["risk_counts"] == {"compliance": 1, "recruiting": 1}
    assert summary["unanswered_count"] == 1

    assert queries_response.status_code == 200
    queries = queries_response.json()["queries"]
    assert [query["text"] for query in queries] == [
        "Can recruiting staff text this prospect?",
        "When do I disclose an NIL deal?",
    ]
    assert all(query["anonymous_user_key"].startswith("anon_") for query in queries)
    assert "Jordan Athlete" not in queries_response.text
    assert "jordan@example.com" not in queries_response.text
    assert "athlete-subject" not in queries_response.text
    assert "storage_key" not in queries_response.text
    assert str(athlete.id) not in queries_response.text


@pytest.mark.asyncio
async def test_admin_analytics_queries_use_plural_filters_before_pagination(
    route_client,
    db_session,
    monkeypatch,
    test_settings,
) -> None:
    organization = await OrganizationRepository(db_session).create(
        name="Playbook Athletics",
        slug="playbook-filtering",
    )
    user_repo = UserRepository(db_session)
    admin = await user_repo.create(
        organization_id=organization.id,
        email="admin-filtering@example.com",
        name="Admin User",
        auth_provider="google",
        provider_subject="admin-filtering-subject",
        role="admin",
    )
    athlete = await user_repo.create(
        organization_id=organization.id,
        email="athlete-filtering@example.com",
        name="Jordan Athlete",
        auth_provider="google",
        provider_subject="athlete-filtering-subject",
        role="athlete",
    )
    window_start = datetime(2026, 6, 1, tzinfo=UTC)
    window_end = datetime(2026, 6, 8, tzinfo=UTC)
    await _seed_turn(
        db_session=db_session,
        organization_id=organization.id,
        athlete_id=athlete.id,
        question="Newer process question",
        created_at=datetime(2026, 6, 6, tzinfo=UTC),
        topic_labels=["process"],
        risk_labels=[],
    )
    await _seed_turn(
        db_session=db_session,
        organization_id=organization.id,
        athlete_id=athlete.id,
        question="Newer housing question",
        created_at=datetime(2026, 6, 5, tzinfo=UTC),
        topic_labels=["housing"],
        risk_labels=[],
    )
    await _seed_turn(
        db_session=db_session,
        organization_id=organization.id,
        athlete_id=athlete.id,
        question="Older NIL compliance question",
        created_at=datetime(2026, 6, 4, tzinfo=UTC),
        topic_labels=["nil"],
        risk_labels=["compliance"],
    )
    await _seed_turn(
        db_session=db_session,
        organization_id=organization.id,
        athlete_id=athlete.id,
        question="Older recruiting compliance question",
        created_at=datetime(2026, 6, 3, tzinfo=UTC),
        topic_labels=["recruiting"],
        risk_labels=["compliance"],
    )
    await _seed_turn(
        db_session=db_session,
        organization_id=organization.id,
        athlete_id=athlete.id,
        question="Older NIL recruiting-risk question",
        created_at=datetime(2026, 6, 2, tzinfo=UTC),
        topic_labels=["nil"],
        risk_labels=["recruiting"],
    )
    monkeypatch.setattr(test_settings, "DASHBOARD_ANALYTICS_MAX_QUERY_ROWS", 2)
    route_client.authenticate_as(admin)

    response = await route_client.client.get(
        "/api/v1/admin/analytics/queries",
        params=[
            ("window_start", window_start.isoformat()),
            ("window_end", window_end.isoformat()),
            ("topic_labels", "nil"),
            ("topic_labels", "recruiting"),
            ("risk_labels", "compliance"),
            ("limit", "10"),
        ],
    )
    page_response = await route_client.client.get(
        "/api/v1/admin/analytics/queries",
        params=[
            ("window_start", window_start.isoformat()),
            ("window_end", window_end.isoformat()),
            ("topic_labels", "nil"),
            ("topic_labels", "recruiting"),
            ("risk_labels", "compliance"),
            ("limit", "1"),
            ("offset", "1"),
        ],
    )

    assert response.status_code == 200
    assert [query["text"] for query in response.json()["queries"]] == [
        "Older NIL compliance question",
        "Older recruiting compliance question",
    ]
    assert page_response.status_code == 200
    assert [query["text"] for query in page_response.json()["queries"]] == [
        "Older recruiting compliance question"
    ]


@pytest.mark.asyncio
async def test_admin_analytics_queries_reject_unsupported_filter_params(
    route_client,
    db_session,
) -> None:
    organization = await OrganizationRepository(db_session).create(
        name="Playbook Athletics",
        slug="playbook-unsupported-filters",
    )
    admin = await UserRepository(db_session).create(
        organization_id=organization.id,
        email="admin-unsupported@example.com",
        name="Admin User",
        auth_provider="google",
        provider_subject="admin-unsupported-subject",
        role="admin",
    )
    route_client.authenticate_as(admin)

    response = await route_client.client.get(
        "/api/v1/admin/analytics/queries",
        params={"unsupported_filter": "nil"},
    )

    assert response.status_code == 422
    assert "unsupported_filter" in response.text


@pytest.mark.asyncio
async def test_admin_analytics_summary_counts_are_not_limited_by_query_row_cap(
    route_client,
    db_session,
    monkeypatch,
    test_settings,
) -> None:
    organization = await OrganizationRepository(db_session).create(
        name="Playbook Athletics",
        slug="playbook-summary-cap",
    )
    user_repo = UserRepository(db_session)
    admin = await user_repo.create(
        organization_id=organization.id,
        email="admin-summary-cap@example.com",
        name="Admin User",
        auth_provider="google",
        provider_subject="admin-summary-cap-subject",
        role="admin",
    )
    athlete = await user_repo.create(
        organization_id=organization.id,
        email="athlete-summary-cap@example.com",
        name="Jordan Athlete",
        auth_provider="google",
        provider_subject="athlete-summary-cap-subject",
        role="athlete",
    )
    window_start = datetime(2026, 6, 1, tzinfo=UTC)
    window_end = datetime(2026, 6, 8, tzinfo=UTC)
    for day in range(1, 5):
        await _seed_turn(
            db_session=db_session,
            organization_id=organization.id,
            athlete_id=athlete.id,
            question=f"NIL question {day}",
            created_at=datetime(2026, 6, day, tzinfo=UTC),
            answer_type="unsupported" if day == 4 else "grounded_answer",
            topic_labels=["nil"],
            risk_labels=["compliance"],
        )
    monkeypatch.setattr(test_settings, "DASHBOARD_ANALYTICS_MAX_QUERY_ROWS", 2)
    route_client.authenticate_as(admin)

    response = await route_client.client.get(
        "/api/v1/admin/analytics/summary",
        params={
            "window_start": window_start.isoformat(),
            "window_end": window_end.isoformat(),
        },
    )

    assert response.status_code == 200
    summary = response.json()
    assert summary["query_volume"] == 4
    assert summary["top_topics"] == [{"label": "nil", "count": 4}]
    assert summary["risk_counts"] == {"compliance": 4}
    assert summary["unanswered_count"] == 1


@pytest.mark.asyncio
async def test_admin_analytics_window_boundaries_and_validation(
    route_client,
    db_session,
) -> None:
    organization = await OrganizationRepository(db_session).create(
        name="Playbook Athletics",
        slug="playbook-window",
    )
    user_repo = UserRepository(db_session)
    admin = await user_repo.create(
        organization_id=organization.id,
        email="admin-window@example.com",
        name="Admin User",
        auth_provider="google",
        provider_subject="admin-window-subject",
        role="admin",
    )
    athlete = await user_repo.create(
        organization_id=organization.id,
        email="athlete-window@example.com",
        name="Jordan Athlete",
        auth_provider="google",
        provider_subject="athlete-window-subject",
        role="athlete",
    )
    window_start = datetime(2026, 6, 1, tzinfo=UTC)
    window_end = datetime(2026, 6, 8, tzinfo=UTC)
    await _seed_turn(
        db_session=db_session,
        organization_id=organization.id,
        athlete_id=athlete.id,
        question="Included start-boundary question",
        created_at=window_start,
        topic_labels=["nil"],
    )
    await _seed_turn(
        db_session=db_session,
        organization_id=organization.id,
        athlete_id=athlete.id,
        question="Excluded end-boundary question",
        created_at=window_end,
        topic_labels=["nil"],
    )
    route_client.authenticate_as(admin)

    summary_response = await route_client.client.get(
        "/api/v1/admin/analytics/summary",
        params={
            "window_start": window_start.isoformat(),
            "window_end": window_end.isoformat(),
        },
    )
    partial_window_response = await route_client.client.get(
        "/api/v1/admin/analytics/summary",
        params={"window_start": window_start.isoformat()},
    )
    oversized_window_response = await route_client.client.get(
        "/api/v1/admin/analytics/summary",
        params={
            "window_start": datetime(2026, 1, 1, tzinfo=UTC).isoformat(),
            "window_end": datetime(2026, 6, 8, tzinfo=UTC).isoformat(),
        },
    )

    assert summary_response.status_code == 200
    assert summary_response.json()["query_volume"] == 1
    assert partial_window_response.status_code == 400
    assert oversized_window_response.status_code == 400


@pytest.mark.asyncio
async def test_admin_dashboard_insight_manual_run_audits_and_dispatches(
    route_client,
    db_session,
    monkeypatch,
) -> None:
    organization = await OrganizationRepository(db_session).create(
        name="Playbook Athletics",
        slug="playbook",
    )
    admin = await UserRepository(db_session).create(
        organization_id=organization.id,
        email="admin@example.com",
        name="Admin User",
        auth_provider="google",
        provider_subject="admin-subject",
        role="admin",
    )
    dispatched: dict[str, object] = {}

    def fake_dispatch(
        self,
        *,
        payload,
    ) -> str:
        dispatched["payload"] = payload
        return "dashboard-task-id"

    monkeypatch.setattr(
        worker_dispatcher.DashboardInsightsTaskDispatcher,
        "dispatch",
        fake_dispatch,
    )
    route_client.authenticate_as(admin)
    window_start = datetime(2026, 6, 1, tzinfo=UTC)
    window_end = datetime(2026, 6, 8, tzinfo=UTC)

    response = await route_client.client.post(
        "/api/v1/admin/dashboard-insights/runs",
        json={
            "window_start": window_start.isoformat(),
            "window_end": window_end.isoformat(),
            "source_filters": {"topic_labels": ["nil"]},
        },
    )

    assert response.status_code == 202
    body = response.json()
    assert body["status"] == "pending"
    assert "run_id" in body
    assert str(dispatched["payload"].run_id) == body["run_id"]

    audit_log = await db_session.scalar(
        select(AuditLog).where(
            AuditLog.action == "dashboard_insight_run.manual_triggered"
        )
    )
    assert audit_log is not None
    assert audit_log.actor_user_id == admin.id
    assert str(audit_log.target_id) == body["run_id"]

    status_response = await route_client.client.get(
        f"/api/v1/admin/dashboard-insights/runs/{body['run_id']}"
    )
    assert status_response.status_code == 200
    assert status_response.json()["status"] == "pending"


@pytest.mark.asyncio
async def test_completed_dashboard_insight_output_routes_use_overlapping_window(
    route_client,
    db_session,
) -> None:
    organization = await OrganizationRepository(db_session).create(
        name="Playbook Athletics",
        slug="playbook",
    )
    admin = await UserRepository(db_session).create(
        organization_id=organization.id,
        email="admin@example.com",
        name="Admin User",
        auth_provider="google",
        provider_subject="admin-subject",
        role="admin",
    )
    run_repo = DashboardInsightRunRepository(db_session)
    insight_repo = DashboardInsightRepository(db_session)
    run = await run_repo.create(
        organization_id=organization.id,
        requested_by=admin.id,
        trigger_type="manual",
        status="completed",
        window_start=datetime(2026, 6, 1, tzinfo=UTC),
        window_end=datetime(2026, 6, 8, tzinfo=UTC),
        source_filters={"topic_labels": ["nil"]},
    )
    output = await insight_repo.create(
        run_id=run.id,
        summary="NIL disclosure timing is the clearest support gap.",
        headline_cards=[
            {
                "title": "NIL disclosure timing",
                "value": "2 related questions",
                "severity": "medium",
            }
        ],
        topic_breakdown=[{"label": "nil", "count": 2, "examples": []}],
        unanswered_questions=[
            {
                "message_id": "00000000-0000-0000-0000-000000000101",
                "text": "What should I do if Playbook cannot answer?",
                "reason": "unsupported",
            }
        ],
        risk_breakdown=[{"label": "compliance", "count": 1}],
        recommended_attention_areas=[
            "Clarify NIL disclosure timing in athlete-facing guidance."
        ],
        source_message_ids=["00000000-0000-0000-0000-000000000101"],
    )
    await db_session.commit()
    route_client.authenticate_as(admin)

    run_response = await route_client.client.get(
        f"/api/v1/admin/dashboard-insights/runs/{run.id}"
    )
    current_response = await route_client.client.get(
        "/api/v1/admin/dashboard-insights/current",
        params={
            "window_start": datetime(2026, 6, 2, tzinfo=UTC).isoformat(),
            "window_end": datetime(2026, 6, 4, tzinfo=UTC).isoformat(),
        },
    )
    outputs_response = await route_client.client.get(
        "/api/v1/admin/dashboard-insights/outputs"
    )
    detail_response = await route_client.client.get(
        f"/api/v1/admin/dashboard-insights/outputs/{output.id}"
    )

    assert run_response.status_code == 200
    run_body = run_response.json()
    assert run_body["status"] == "completed"
    assert run_body["output"]["id"] == str(output.id)
    assert run_body["output"]["summary"] == output.summary

    assert current_response.status_code == 200
    assert current_response.json()["id"] == str(output.id)
    assert current_response.json()["unanswered_questions"][0]["reason"] == "unsupported"

    assert outputs_response.status_code == 200
    assert [item["id"] for item in outputs_response.json()] == [str(output.id)]

    assert detail_response.status_code == 200
    assert detail_response.json()["risk_breakdown"] == [{"label": "compliance", "count": 1}]


@pytest.mark.asyncio
async def test_failed_dashboard_insight_run_is_visible_with_sanitized_error(
    route_client,
    db_session,
) -> None:
    organization = await OrganizationRepository(db_session).create(
        name="Playbook Athletics",
        slug="playbook-failed",
    )
    admin = await UserRepository(db_session).create(
        organization_id=organization.id,
        email="admin-failed@example.com",
        name="Admin User",
        auth_provider="google",
        provider_subject="admin-failed-subject",
        role="admin",
    )
    run = await DashboardInsightRunRepository(db_session).create(
        organization_id=organization.id,
        requested_by=admin.id,
        trigger_type="manual",
        status="failed",
        window_start=datetime(2026, 6, 1, tzinfo=UTC),
        window_end=datetime(2026, 6, 8, tzinfo=UTC),
        source_filters={},
    )
    await DashboardInsightRunRepository(db_session).update_status(
        run,
        status="failed",
        error_message="RuntimeError",
    )
    await db_session.commit()
    route_client.authenticate_as(admin)

    response = await route_client.client.get(
        f"/api/v1/admin/dashboard-insights/runs/{run.id}"
    )

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "failed"
    assert body["error_message"] == "RuntimeError"
    assert "secret" not in response.text.lower()


@pytest.mark.asyncio
async def test_nightly_dashboard_insight_schedule_dispatches_active_org_runs(
    db_session,
) -> None:
    organization_repo = OrganizationRepository(db_session)
    active_org = await organization_repo.create(
        name="Playbook Athletics",
        slug="playbook",
    )
    await organization_repo.create(
        name="Inactive Athletics",
        slug="inactive",
        is_active=False,
    )
    dispatched_payloads: list[object] = []

    class RecordingDispatcher:
        def dispatch(self, *, payload) -> str:
            dispatched_payloads.append(payload)
            return "dashboard-task-id"

    service = DashboardInsightService(
        db_session,
        dispatcher=RecordingDispatcher(),
    )

    first_result = await service.schedule_nightly_runs()
    second_result = await service.schedule_nightly_runs()

    assert first_result.to_payload() == {
        "status": "scheduled",
        "created": 1,
        "dispatched": 1,
        "skipped": 0,
    }
    assert second_result.to_payload() == {
        "status": "scheduled",
        "created": 0,
        "dispatched": 0,
        "skipped": 1,
    }
    assert len(dispatched_payloads) == 1
    assert dispatched_payloads[0].organization_id == active_org.id

    runs = list(
        (
            await db_session.scalars(
                select(DashboardInsightRun).where(
                    DashboardInsightRun.organization_id == active_org.id
                )
            )
        ).all()
    )
    assert len(runs) == 1
    assert runs[0].trigger_type == "nightly"
    assert runs[0].status == "pending"


@pytest.mark.asyncio
async def test_admin_analytics_routes_reject_athletes(route_client, db_session) -> None:
    organization = await OrganizationRepository(db_session).create(
        name="Playbook Athletics",
        slug="playbook",
    )
    athlete = await UserRepository(db_session).create(
        organization_id=organization.id,
        email="athlete@example.com",
        name="Jordan Athlete",
        auth_provider="google",
        provider_subject="athlete-subject",
        role="athlete",
    )
    route_client.authenticate_as(athlete)

    response = await route_client.client.get("/api/v1/admin/analytics/summary")

    assert response.status_code == 403


@pytest.mark.asyncio
async def test_dashboard_insight_routes_reject_athletes(route_client, db_session) -> None:
    organization = await OrganizationRepository(db_session).create(
        name="Playbook Athletics",
        slug="playbook-athlete-denied",
    )
    athlete = await UserRepository(db_session).create(
        organization_id=organization.id,
        email="athlete-dashboard@example.com",
        name="Jordan Athlete",
        auth_provider="google",
        provider_subject="athlete-dashboard-subject",
        role="athlete",
    )
    route_client.authenticate_as(athlete)

    current_response = await route_client.client.get(
        "/api/v1/admin/dashboard-insights/current"
    )
    create_response = await route_client.client.post(
        "/api/v1/admin/dashboard-insights/runs",
        json={
            "window_start": datetime(2026, 6, 1, tzinfo=UTC).isoformat(),
            "window_end": datetime(2026, 6, 8, tzinfo=UTC).isoformat(),
            "source_filters": {},
        },
    )

    assert current_response.status_code == 403
    assert create_response.status_code == 403
