"""Route-level tests for athlete conversation endpoints."""

from __future__ import annotations

from uuid import UUID

import pytest

from app.repositories.conversations import (
    ConversationFileChunkRepository,
    ConversationFileRepository,
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
        json={"initial_message": " Can I accept this NIL deal? "},
    )

    assert create_response.status_code == 201
    conversation_id = create_response.json()["id"]
    conversation_uuid = UUID(conversation_id)
    assert create_response.json()["athlete_id"] == str(athlete.id)
    assert create_response.json()["title"] is None
    assert create_response.json()["last_message_at"] is not None
    assert create_response.json()["messages"][0]["role"] == "user"
    assert create_response.json()["messages"][0]["content"] == (
        "Can I accept this NIL deal?"
    )
    assert create_response.json()["files"] == []

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
    file = await ConversationFileRepository(db_session).create(
        conversation_id=conversation_uuid,
        uploaded_by=athlete.id,
        filename="nil-contract.pdf",
        content_type="application/pdf",
        size_bytes=123456,
        storage_key="conversations/org/conversation/file/nil-contract.pdf",
        message_id=message.id,
    )
    await ConversationFileChunkRepository(db_session).create(
        file_id=file.id,
        chunk_index=1,
        text="Contract excerpt",
        token_count=2,
    )

    list_response = await route_client.client.get("/api/v1/conversations")
    detail_response = await route_client.client.get(
        f"/api/v1/conversations/{conversation_id}"
    )

    assert list_response.status_code == 200
    assert [row["id"] for row in list_response.json()] == [conversation_id]
    assert list_response.json()[0]["title"] is None
    assert list_response.json()[0]["last_message_at"] is not None
    assert detail_response.status_code == 200
    assert detail_response.json()["messages"][0]["role"] == "user"
    assert detail_response.json()["messages"][1]["id"] == str(message.id)
    assert detail_response.json()["messages"][1]["citations"][0]["id"] == str(
        citation.id
    )
    assert detail_response.json()["files"] == [
        {
            "id": str(file.id),
            "conversation_id": conversation_id,
            "message_id": str(message.id),
            "filename": "nil-contract.pdf",
            "content_type": "application/pdf",
            "size_bytes": 123456,
            "extraction_status": "uploaded",
            "chunk_count": 1,
            "created_at": file.created_at.isoformat().replace("+00:00", "Z"),
            "updated_at": file.updated_at.isoformat().replace("+00:00", "Z"),
        }
    ]
    assert "storage_key" not in detail_response.json()["files"][0]
    assert "extracted_text_ref" not in detail_response.json()["files"][0]


@pytest.mark.asyncio
async def test_create_conversation_validates_initial_message(
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

    response = await route_client.client.post(
        "/api/v1/conversations",
        json={"initial_message": "   "},
        headers={"X-Request-ID": "req-initial-message"},
    )

    assert response.status_code == 422
    error = response.json()["error"]
    assert error["code"] == "VALIDATION_ERROR"
    assert error["details"]["request_id"] == "req-initial-message"


@pytest.mark.asyncio
async def test_conversation_create_openapi_uses_initial_message(route_client) -> None:
    response = await route_client.client.get("/openapi.json")

    assert response.status_code == 200
    schema = response.json()["components"]["schemas"]["ConversationCreateRequest"]
    detail_schema = response.json()["components"]["schemas"][
        "ConversationDetailResponse"
    ]
    assert "initial_message" in schema["properties"]
    assert "title" not in schema["properties"]
    assert "initial_message" in schema["required"]
    assert "files" in detail_schema["properties"]


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
