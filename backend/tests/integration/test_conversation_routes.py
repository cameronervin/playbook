"""Route-level tests for athlete conversation shell endpoints."""

from __future__ import annotations

from uuid import UUID

import pytest

from app.repositories.conversations import (
    ConversationMessageRepository,
    ConversationRepository,
    MessageCitationRepository,
)
from app.repositories.identity import OrganizationRepository, UserRepository


@pytest.mark.asyncio
async def test_athlete_conversation_routes_create_list_and_get_detail(
    route_client,
    db_session,
) -> None:
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
        sport_team="Basketball",
    )
    route_client.authenticate_as(athlete)

    create_response = await route_client.client.post(
        "/api/v1/conversations",
        json={"title": "NIL question"},
    )

    assert create_response.status_code == 201
    conversation_id = create_response.json()["id"]
    conversation_uuid = UUID(conversation_id)
    assert create_response.json()["athlete_id"] == str(athlete.id)

    message = await ConversationMessageRepository(db_session).create(
        conversation_id=conversation_uuid,
        role="assistant",
        content="Check the NIL handbook.",
        topic_labels=["nil"],
    )
    citation = await MessageCitationRepository(db_session).create(
        message_id=message.id,
        source_title="NIL Handbook",
        rank=1,
    )

    list_response = await route_client.client.get("/api/v1/conversations")
    detail_response = await route_client.client.get(
        f"/api/v1/conversations/{conversation_id}"
    )

    assert list_response.status_code == 200
    assert [row["id"] for row in list_response.json()] == [conversation_id]
    assert detail_response.status_code == 200
    assert detail_response.json()["messages"][0]["id"] == str(message.id)
    assert detail_response.json()["messages"][0]["citations"][0]["id"] == str(
        citation.id
    )


@pytest.mark.asyncio
async def test_conversation_detail_is_scoped_to_current_athlete(
    route_client,
    db_session,
) -> None:
    organization = await OrganizationRepository(db_session).create(
        name="Playbook Athletics",
        slug="playbook",
    )
    user_repo = UserRepository(db_session)
    owner = await user_repo.create(
        organization_id=organization.id,
        email="owner@example.com",
        name="Owner Athlete",
        auth_provider="google",
        provider_subject="owner-subject",
    )
    other = await user_repo.create(
        organization_id=organization.id,
        email="other@example.com",
        name="Other Athlete",
        auth_provider="google",
        provider_subject="other-subject",
    )
    conversation = await ConversationRepository(db_session).create(
        organization_id=organization.id,
        athlete_id=owner.id,
        title="Private NIL question",
    )
    route_client.authenticate_as(other)

    response = await route_client.client.get(
        f"/api/v1/conversations/{conversation.id}",
        headers={"X-Request-ID": "req-convo-owner"},
    )

    assert response.status_code == 404
    assert response.json()["error"] == {
        "code": "NOT_FOUND",
        "message": f"Conversation not found: {conversation.id}",
        "retryable": False,
        "details": {"request_id": "req-convo-owner"},
    }


@pytest.mark.asyncio
async def test_conversation_routes_require_athlete_role(route_client, db_session) -> None:
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

    response = await route_client.client.get(
        "/api/v1/conversations",
        headers={"X-Request-ID": "req-convo-role"},
    )

    assert response.status_code == 403
    assert response.json()["error"] == {
        "code": "FORBIDDEN",
        "message": "Athlete role required",
        "retryable": False,
        "details": {"request_id": "req-convo-role"},
    }
