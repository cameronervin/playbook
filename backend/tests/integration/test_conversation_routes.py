"""Route-level tests for athlete conversation endpoints."""

from __future__ import annotations

from types import SimpleNamespace
from uuid import UUID

import pytest

from app.api.v1.dependencies import get_agent_stream_service
from app.infrastructure.streaming import InMemoryAgentStreamProvider
from app.repositories.conversations import (
    ConversationFileChunkRepository,
    ConversationFileRepository,
    ConversationMessageRepository,
    ConversationRepository,
    MessageCitationRepository,
)
from app.repositories.identity import OrganizationRepository, UserRepository
from app.services.agent_stream_service import AgentStreamService
from app.workers import tasks as worker_tasks


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
async def test_submit_message_persists_placeholder_and_dispatches_task(
    route_client,
    db_session,
    monkeypatch,
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
        provider_subject="athlete-submit-subject",
        sport_team="Basketball",
    )
    conversation = await ConversationRepository(db_session).create(
        organization_id=organization.id,
        athlete_id=athlete.id,
        title="NIL question",
    )
    file = await ConversationFileRepository(db_session).create(
        conversation_id=conversation.id,
        uploaded_by=athlete.id,
        filename="nil-contract.pdf",
        content_type="application/pdf",
        size_bytes=123456,
        storage_key="conversations/org/conversation/file/nil-contract.pdf",
    )
    route_client.authenticate_as(athlete)
    dispatched: dict[str, object] = {}

    def fake_apply_async(*, kwargs: dict[str, object], task_id: str) -> SimpleNamespace:
        dispatched["kwargs"] = kwargs
        dispatched["task_id"] = task_id
        return SimpleNamespace(id=task_id)

    monkeypatch.setattr(
        worker_tasks.run_athlete_chat_task,
        "apply_async",
        fake_apply_async,
    )

    response = await route_client.client.post(
        f"/api/v1/conversations/{conversation.id}/messages",
        json={
            "content": " Can I still accept this NIL deal? ",
            "file_ids": [str(file.id)],
        },
    )

    assert response.status_code == 202
    body = response.json()
    assert body["status"] == "streaming"
    assert body["stream_url"] == (
        f"/api/v1/conversations/{conversation.id}/messages/"
        f"{body['assistant_message_id']}/stream?task_id={body['task_id']}"
    )
    assert dispatched["task_id"] == body["task_id"]
    assert dispatched["kwargs"] == {
        "conversation_id": str(conversation.id),
        "athlete_user_id": str(athlete.id),
        "user_message_id": body["user_message_id"],
        "assistant_message_id": body["assistant_message_id"],
        "organization_id": str(organization.id),
        "attached_file_ids": [str(file.id)],
    }

    messages = await ConversationMessageRepository(db_session).list_by_conversation(
        conversation.id
    )
    assert [message.role for message in messages] == ["user", "assistant"]
    assert messages[0].id == UUID(body["user_message_id"])
    assert messages[0].content == "Can I still accept this NIL deal?"
    assert messages[0].status == "complete"
    assert messages[0].message_metadata == {"attached_file_ids": [str(file.id)]}
    assert messages[1].id == UUID(body["assistant_message_id"])
    assert messages[1].content == ""
    assert messages[1].status == "streaming"
    assert messages[1].message_metadata["task_id"] == body["task_id"]
    assert messages[1].message_metadata["user_message_id"] == body["user_message_id"]
    assert conversation.last_message_at == messages[0].created_at


@pytest.mark.asyncio
async def test_submit_message_validates_content(route_client, db_session) -> None:
    organization = await OrganizationRepository(db_session).create(
        name="Playbook Athletics",
        slug="playbook",
    )
    athlete = await UserRepository(db_session).create(
        organization_id=organization.id,
        email="athlete@example.com",
        name="Jordan Athlete",
        auth_provider="google",
        provider_subject="athlete-blank-submit",
    )
    conversation = await ConversationRepository(db_session).create(
        organization_id=organization.id,
        athlete_id=athlete.id,
    )
    route_client.authenticate_as(athlete)

    response = await route_client.client.post(
        f"/api/v1/conversations/{conversation.id}/messages",
        json={"content": "   "},
        headers={"X-Request-ID": "req-submit-blank"},
    )

    assert response.status_code == 422
    error = response.json()["error"]
    assert error["code"] == "VALIDATION_ERROR"
    assert error["details"]["request_id"] == "req-submit-blank"


@pytest.mark.asyncio
async def test_submit_message_is_scoped_to_current_athlete(
    route_client,
    db_session,
    monkeypatch,
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
        provider_subject="owner-submit-subject",
    )
    other = await user_repo.create(
        organization_id=organization.id,
        email="other@example.com",
        name="Other Athlete",
        auth_provider="google",
        provider_subject="other-submit-subject",
    )
    conversation = await ConversationRepository(db_session).create(
        organization_id=organization.id,
        athlete_id=owner.id,
        title="Private NIL question",
    )
    route_client.authenticate_as(other)

    def fail_apply_async(**_: object) -> None:
        pytest.fail("submit must not dispatch for another athlete's conversation")

    monkeypatch.setattr(
        worker_tasks.run_athlete_chat_task,
        "apply_async",
        fail_apply_async,
    )

    response = await route_client.client.post(
        f"/api/v1/conversations/{conversation.id}/messages",
        json={"content": "Can I follow up?"},
        headers={"X-Request-ID": "req-submit-owner"},
    )

    assert response.status_code == 404
    assert response.json()["error"] == {
        "code": "NOT_FOUND",
        "message": f"Conversation not found: {conversation.id}",
        "retryable": False,
        "details": {"request_id": "req-submit-owner"},
    }


@pytest.mark.asyncio
async def test_submit_message_rejects_files_outside_conversation(
    route_client,
    db_session,
    monkeypatch,
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
        provider_subject="athlete-file-submit-subject",
    )
    conversation = await ConversationRepository(db_session).create(
        organization_id=organization.id,
        athlete_id=athlete.id,
    )
    other_conversation = await ConversationRepository(db_session).create(
        organization_id=organization.id,
        athlete_id=athlete.id,
    )
    other_file = await ConversationFileRepository(db_session).create(
        conversation_id=other_conversation.id,
        uploaded_by=athlete.id,
        filename="other.pdf",
        content_type="application/pdf",
        size_bytes=1,
        storage_key="conversations/org/other/file/other.pdf",
    )
    route_client.authenticate_as(athlete)

    def fail_apply_async(**_: object) -> None:
        pytest.fail("submit must not dispatch when file_ids are invalid")

    monkeypatch.setattr(
        worker_tasks.run_athlete_chat_task,
        "apply_async",
        fail_apply_async,
    )

    response = await route_client.client.post(
        f"/api/v1/conversations/{conversation.id}/messages",
        json={"content": "Use this file", "file_ids": [str(other_file.id)]},
        headers={"X-Request-ID": "req-submit-file"},
    )

    assert response.status_code == 400
    assert response.json()["error"] == {
        "code": "VALIDATION_ERROR",
        "message": "One or more file_ids are not available for this conversation",
        "retryable": False,
        "details": {"request_id": "req-submit-file"},
    }


@pytest.mark.asyncio
async def test_stream_message_emits_seeded_sse_events(
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
        provider_subject="athlete-stream-subject",
    )
    conversation = await ConversationRepository(db_session).create(
        organization_id=organization.id,
        athlete_id=athlete.id,
    )
    assistant_message = await ConversationMessageRepository(db_session).create(
        conversation_id=conversation.id,
        role="assistant",
        content="",
        status="streaming",
        metadata={"task_id": "task-stream-123"},
    )
    provider = InMemoryAgentStreamProvider()
    stream_service = AgentStreamService(provider)
    await stream_service.publish_progress("task-stream-123", status="retrieving")
    await stream_service.publish_chunk("task-stream-123", content="Hello")
    await stream_service.publish_complete(
        "task-stream-123",
        data={"assistant_message_id": str(assistant_message.id)},
    )
    route_client.app.dependency_overrides[get_agent_stream_service] = (
        lambda: AgentStreamService(provider)
    )
    route_client.authenticate_as(athlete)

    response = await route_client.client.get(
        f"/api/v1/conversations/{conversation.id}/messages/"
        f"{assistant_message.id}/stream?task_id=task-stream-123"
    )

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/event-stream")
    assert response.headers["cache-control"] == "no-cache"
    assert response.headers["x-accel-buffering"] == "no"
    assert "id: 1-0\nevent: progress\n" in response.text
    assert "id: 2-0\nevent: chunk\n" in response.text
    assert '"content":"Hello"' in response.text
    assert "id: 3-0\nevent: complete\n" in response.text


@pytest.mark.asyncio
async def test_stream_message_resumes_from_after_id_and_last_event_id(
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
        provider_subject="athlete-stream-resume-subject",
    )
    conversation = await ConversationRepository(db_session).create(
        organization_id=organization.id,
        athlete_id=athlete.id,
    )
    assistant_message = await ConversationMessageRepository(db_session).create(
        conversation_id=conversation.id,
        role="assistant",
        content="",
        status="streaming",
        metadata={"task_id": "task-stream-resume"},
    )
    provider = InMemoryAgentStreamProvider()
    stream_service = AgentStreamService(provider)
    await stream_service.publish_chunk("task-stream-resume", content="first")
    await stream_service.publish_chunk("task-stream-resume", content="second")
    await stream_service.publish_complete("task-stream-resume")
    route_client.app.dependency_overrides[get_agent_stream_service] = (
        lambda: AgentStreamService(provider)
    )
    route_client.authenticate_as(athlete)

    response = await route_client.client.get(
        f"/api/v1/conversations/{conversation.id}/messages/"
        f"{assistant_message.id}/stream?task_id=task-stream-resume&after_id=0-0",
        headers={"Last-Event-ID": "1-0"},
    )

    assert response.status_code == 200
    assert "id: 1-0" not in response.text
    assert "id: 2-0\nevent: chunk\n" in response.text
    assert '"content":"second"' in response.text
    assert "id: 3-0\nevent: complete\n" in response.text


@pytest.mark.asyncio
async def test_stream_message_validates_athlete_message_and_task_binding(
    route_client,
    db_session,
) -> None:
    organization = await OrganizationRepository(db_session).create(
        name="Playbook Athletics",
        slug="playbook",
    )
    owner = await UserRepository(db_session).create(
        organization_id=organization.id,
        email="owner@example.com",
        name="Owner Athlete",
        auth_provider="google",
        provider_subject="athlete-stream-owner",
    )
    other = await UserRepository(db_session).create(
        organization_id=organization.id,
        email="other@example.com",
        name="Other Athlete",
        auth_provider="google",
        provider_subject="athlete-stream-other",
    )
    conversation = await ConversationRepository(db_session).create(
        organization_id=organization.id,
        athlete_id=owner.id,
    )
    assistant_message = await ConversationMessageRepository(db_session).create(
        conversation_id=conversation.id,
        role="assistant",
        content="",
        status="streaming",
        metadata={"task_id": "task-owner"},
    )
    route_client.app.dependency_overrides[get_agent_stream_service] = (
        lambda: AgentStreamService(InMemoryAgentStreamProvider())
    )

    route_client.authenticate_as(owner)
    wrong_task_response = await route_client.client.get(
        f"/api/v1/conversations/{conversation.id}/messages/"
        f"{assistant_message.id}/stream?task_id=wrong-task",
        headers={"X-Request-ID": "req-wrong-task"},
    )
    route_client.authenticate_as(other)
    wrong_athlete_response = await route_client.client.get(
        f"/api/v1/conversations/{conversation.id}/messages/"
        f"{assistant_message.id}/stream?task_id=task-owner",
        headers={"X-Request-ID": "req-wrong-athlete"},
    )

    assert wrong_task_response.status_code == 404
    assert wrong_task_response.json()["error"]["code"] == "NOT_FOUND"
    assert wrong_task_response.json()["error"]["details"]["request_id"] == (
        "req-wrong-task"
    )
    assert wrong_athlete_response.status_code == 404
    assert wrong_athlete_response.json()["error"]["code"] == "NOT_FOUND"
    assert wrong_athlete_response.json()["error"]["details"]["request_id"] == (
        "req-wrong-athlete"
    )


@pytest.mark.asyncio
async def test_conversation_create_openapi_uses_initial_message(route_client) -> None:
    response = await route_client.client.get("/openapi.json")

    assert response.status_code == 200
    schema = response.json()["components"]["schemas"]["ConversationCreateRequest"]
    submit_schema = response.json()["components"]["schemas"]["MessageSubmitRequest"]
    submit_response_schema = response.json()["components"]["schemas"][
        "MessageSubmitResponse"
    ]
    detail_schema = response.json()["components"]["schemas"][
        "ConversationDetailResponse"
    ]
    assert "initial_message" in schema["properties"]
    assert "title" not in schema["properties"]
    assert "initial_message" in schema["required"]
    assert "content" in submit_schema["properties"]
    assert "file_ids" in submit_schema["properties"]
    assert "content" in submit_schema["required"]
    assert "task_id" in submit_response_schema["properties"]
    assert "stream_url" in submit_response_schema["properties"]
    assert "files" in detail_schema["properties"]
    assert (
        "/api/v1/conversations/{conversation_id}/messages/{message_id}/stream"
        in response.json()["paths"]
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
