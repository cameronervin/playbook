"""Integration tests for admin chat side-panel APIs."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import UUID

import pytest
from sqlalchemy import select

from app.api.v1.dependencies import get_agent_stream_service
from app.infrastructure.streaming import InMemoryAgentStreamProvider
from app.models.analytics import AdminChatMessage, AdminChatSession
from app.models.audit import AuditLog
from app.repositories.conversations import (
    ConversationMessageRepository,
    ConversationRepository,
)
from app.repositories.identity import OrganizationRepository, UserRepository
from app.services.agent_stream_service import AgentStreamService
from app.workers import dispatcher as worker_dispatcher


async def _seed_analytics_turn(
    *,
    db_session,
    organization_id,
    athlete_id,
    question: str = "When do I disclose an NIL deal?",
    created_at: datetime = datetime(2026, 6, 2, tzinfo=UTC),
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
    await message_repo.create(
        conversation_id=conversation.id,
        role="assistant",
        content="Assistant response",
        status="complete",
        safety_outcome="grounded_answer",
        topic_labels=["nil"],
        risk_labels=["compliance"],
        metadata={
            "user_message_id": str(user_message.id),
            "answer_type": "grounded_answer",
        },
        created_at=created_at + timedelta(microseconds=1),
    )


@pytest.mark.asyncio
async def test_admin_chat_session_message_and_stream_contract(
    route_client,
    db_session,
    monkeypatch,
) -> None:
    organization = await OrganizationRepository(db_session).create(
        name="Playbook Athletics",
        slug="playbook",
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
        email="athlete@example.com",
        name="Athlete User",
        auth_provider="google",
        provider_subject="athlete-subject",
        role="athlete",
    )
    await _seed_analytics_turn(
        db_session=db_session,
        organization_id=organization.id,
        athlete_id=athlete.id,
    )
    dispatched: dict[str, object] = {}

    def fake_dispatch(self, *, task_id: str, payload) -> str:
        dispatched["task_id"] = task_id
        dispatched["payload"] = payload
        return task_id

    monkeypatch.setattr(
        worker_dispatcher.AdminChatTaskDispatcher,
        "dispatch",
        fake_dispatch,
        raising=False,
    )
    route_client.authenticate_as(admin)
    window_start = datetime(2026, 6, 1, tzinfo=UTC)
    window_end = datetime(2026, 6, 8, tzinfo=UTC)

    create_response = await route_client.client.post(
        "/api/v1/admin/chat/sessions",
        json={
            "title": "Weekly NIL questions",
            "context_window_start": window_start.isoformat(),
            "context_window_end": window_end.isoformat(),
        },
    )

    assert create_response.status_code == 201
    session_body = create_response.json()
    session_id = UUID(session_body["id"])
    assert session_body["title"] == "Weekly NIL questions"
    assert session_body["status"] == "active"

    submit_response = await route_client.client.post(
        f"/api/v1/admin/chat/sessions/{session_id}/messages",
        json={
            "question": "What are athletes most confused about this week?",
            "window": "7d",
        },
    )

    assert submit_response.status_code == 202
    submit_body = submit_response.json()
    assert submit_body["session_id"] == str(session_id)
    assert submit_body["status"] == "streaming"
    assert submit_body["task_id"] == dispatched["task_id"]
    assert submit_body["stream_url"].endswith(f"?task_id={submit_body['task_id']}")
    payload = dispatched["payload"]
    assert payload.session_id == session_id
    assert payload.admin_user_id == admin.id
    assert payload.organization_id == organization.id
    assert payload.window_start is not None
    assert payload.window_end is not None

    session = await db_session.get(AdminChatSession, session_id)
    assert session is not None
    assert session.last_message_at is not None
    messages = list(
        (
            await db_session.scalars(
                select(AdminChatMessage)
                .where(AdminChatMessage.session_id == session_id)
                .order_by(AdminChatMessage.created_at.asc(), AdminChatMessage.id.asc())
            )
        ).all()
    )
    assert [message.role for message in messages] == ["user", "assistant"]
    assert messages[0].content == "What are athletes most confused about this week?"
    assert messages[1].status == "streaming"
    assert messages[1].message_metadata["task_id"] == submit_body["task_id"]

    detail_response = await route_client.client.get(
        f"/api/v1/admin/chat/sessions/{session_id}"
    )
    assert detail_response.status_code == 200
    assert [message["role"] for message in detail_response.json()["messages"]] == [
        "user",
        "assistant",
    ]

    provider = InMemoryAgentStreamProvider()
    stream_service = AgentStreamService(provider)
    await stream_service.publish_complete(
        submit_body["task_id"],
        data={"assistant_message_id": submit_body["assistant_message_id"]},
    )
    route_client.app.dependency_overrides[get_agent_stream_service] = (
        lambda: AgentStreamService(provider)
    )
    stream_response = await route_client.client.get(
        f"/api/v1/admin/chat/sessions/{session_id}/messages/"
        f"{submit_body['assistant_message_id']}/stream",
        params={"task_id": submit_body["task_id"]},
    )
    assert stream_response.status_code == 200
    assert stream_response.headers["content-type"].startswith("text/event-stream")

    bad_stream_response = await route_client.client.get(
        f"/api/v1/admin/chat/sessions/{session_id}/messages/"
        f"{submit_body['assistant_message_id']}/stream",
        params={"task_id": "wrong-task-id"},
    )
    assert bad_stream_response.status_code == 404

    audit_actions = {
        row.action
        for row in (
            await db_session.scalars(
                select(AuditLog).where(AuditLog.organization_id == organization.id)
            )
        ).all()
    }
    assert {
        "admin_chat.session_created",
        "admin_chat.question_submitted",
    }.issubset(audit_actions)


@pytest.mark.asyncio
async def test_admin_chat_routes_reject_athletes(route_client, db_session) -> None:
    organization = await OrganizationRepository(db_session).create(
        name="Playbook Athletics",
        slug="playbook",
    )
    athlete = await UserRepository(db_session).create(
        organization_id=organization.id,
        email="athlete@example.com",
        name="Athlete User",
        auth_provider="google",
        provider_subject="athlete-subject",
        role="athlete",
    )
    route_client.authenticate_as(athlete)

    response = await route_client.client.get("/api/v1/admin/chat/sessions")

    assert response.status_code == 403


@pytest.mark.asyncio
async def test_admin_chat_message_rejects_conflicting_window_fields(
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
    route_client.authenticate_as(admin)
    create_response = await route_client.client.post(
        "/api/v1/admin/chat/sessions",
        json={"title": "Weekly NIL questions"},
    )
    session_id = create_response.json()["id"]

    response = await route_client.client.post(
        f"/api/v1/admin/chat/sessions/{session_id}/messages",
        json={
            "question": "What changed?",
            "window": "7d",
            "window_start": "2026-06-01T00:00:00Z",
            "window_end": "2026-06-08T00:00:00Z",
        },
    )

    assert response.status_code == 422
