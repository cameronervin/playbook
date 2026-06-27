"""Unit tests for Phase 1 backend services."""

from __future__ import annotations

from datetime import UTC, datetime
import hashlib
import hmac
from types import SimpleNamespace
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest

from app.core.exceptions import ForbiddenError
from app.models.identity import User
from app.schemas.kb_documents import KBWebhookPayload
from app.schemas.users import UpdateProfileRequest, UpdateUserRoleRequest
from app.services.kb_documents import KBDocumentWebhookService
from app.services.user_service import UserAdminService, UserProfileService


def _user(role: str = "athlete") -> User:
    return User(
        id=uuid4(),
        organization_id=uuid4(),
        email=f"{role}@example.com",
        name=f"{role.title()} User",
        role=role,
        auth_provider="google",
        provider_subject=f"{role}-subject",
        is_active=True,
        is_verified=True,
        is_superuser=role == "super_admin",
        created_at=datetime.now(UTC),
    )


@pytest.mark.asyncio
async def test_profile_completion_returns_chat_route() -> None:
    session = SimpleNamespace(commit=AsyncMock())
    athlete = _user("athlete")
    athlete.sport_team = None
    user_repo = SimpleNamespace(update_profile=AsyncMock())

    async def update_profile(user: User, *, name: str, sport_team: str) -> User:
        user.name = name
        user.sport_team = sport_team
        return user

    user_repo.update_profile.side_effect = update_profile
    service = UserProfileService(session, user_repo=user_repo)

    response = await service.update_profile(
        user=athlete,
        request=UpdateProfileRequest(
            name=" Jordan Athlete ",
            sport_team=" Basketball ",
        ),
    )

    user_repo.update_profile.assert_awaited_once_with(
        athlete,
        name="Jordan Athlete",
        sport_team="Basketball",
    )
    session.commit.assert_awaited_once()
    assert response.profile_complete is True
    assert response.next_route == "/chat"


@pytest.mark.asyncio
async def test_role_update_syncs_audit_and_commit() -> None:
    session = SimpleNamespace(commit=AsyncMock())
    actor = _user("super_admin")
    target = _user("athlete")
    target.organization_id = actor.organization_id
    user_repo = SimpleNamespace(get=AsyncMock(return_value=target), update_role=AsyncMock())
    audit_service = SimpleNamespace(record=AsyncMock())

    async def update_role(user: User, *, role: str) -> User:
        user.role = role
        user.is_superuser = role == "super_admin"
        return user

    user_repo.update_role.side_effect = update_role
    service = UserAdminService(
        session,
        user_repo=user_repo,
        audit_service=audit_service,
    )

    response = await service.update_role(
        actor=actor,
        user_id=target.id,
        request=UpdateUserRoleRequest(role="super_admin"),
    )

    user_repo.update_role.assert_awaited_once_with(target, role="super_admin")
    audit_service.record.assert_awaited_once()
    session.commit.assert_awaited_once()
    assert response.role == "super_admin"
    assert target.is_superuser is True


@pytest.mark.asyncio
async def test_kb_webhook_verifies_signature_and_updates_status(
    monkeypatch,
    test_settings,
) -> None:
    monkeypatch.setattr(test_settings, "KB_WEBHOOK_SECRET", "webhook-secret")
    document = SimpleNamespace(
        id=uuid4(),
        organization_id=uuid4(),
        processing_status="processing",
        failure_reason=None,
    )
    document_repo = SimpleNamespace(
        get=AsyncMock(return_value=document),
        get_by_kb_service_document_id=AsyncMock(return_value=None),
        update_status=AsyncMock(),
    )
    event_repo = SimpleNamespace(create=AsyncMock())
    session = SimpleNamespace(commit=AsyncMock())
    service = KBDocumentWebhookService(
        session,
        settings=test_settings,
        document_repo=document_repo,
        event_repo=event_repo,
    )
    payload = KBWebhookPayload(
        document_id=document.id,
        stage="pipeline",
        status="success",
        timestamp=None,
        metadata={"task_id": "task-1"},
    )
    raw_body = payload.model_dump_json().encode()
    signature = "sha256=" + hmac.new(
        test_settings.KB_WEBHOOK_SECRET.encode(),
        raw_body,
        hashlib.sha256,
    ).hexdigest()

    response = await service.process(
        payload=payload,
        raw_body=raw_body,
        signature=signature,
    )

    document_repo.update_status.assert_awaited_once_with(
        document,
        processing_status="ready",
        failure_reason=None,
    )
    event_repo.create.assert_awaited_once()
    session.commit.assert_awaited_once()
    assert response.document_status == "ready"


@pytest.mark.asyncio
async def test_kb_webhook_rejects_invalid_signature(monkeypatch, test_settings) -> None:
    monkeypatch.setattr(test_settings, "KB_WEBHOOK_SECRET", "webhook-secret")
    service = KBDocumentWebhookService(
        SimpleNamespace(commit=AsyncMock()),
        settings=test_settings,
        document_repo=SimpleNamespace(),
        event_repo=SimpleNamespace(),
    )
    payload = KBWebhookPayload(
        document_id=uuid4(),
        stage="pipeline",
        status="success",
    )

    with pytest.raises(ForbiddenError):
        await service.process(
            payload=payload,
            raw_body=payload.model_dump_json().encode(),
            signature="sha256=bad",
        )
