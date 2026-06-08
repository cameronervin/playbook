"""Route-level tests for signed KB service webhook handling."""

from __future__ import annotations

import hashlib
import hmac
import json
import time

import pytest

from app.core.config import settings
from app.repositories.identity import OrganizationRepository, UserRepository
from app.repositories.knowledge_base import KBDocumentEventRepository, KBDocumentRepository


async def _document(db_session):
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
    return await KBDocumentRepository(db_session).create(
        organization_id=organization.id,
        uploaded_by=admin.id,
        title="NIL Handbook",
        filename="nil-handbook.pdf",
        content_type="application/pdf",
        size_bytes=123,
        storage_key="kb/originals/nil-handbook.pdf",
    )


def _signed_body(payload: dict, secret: str) -> tuple[bytes, str]:
    body = json.dumps(payload, separators=(",", ":")).encode()
    signature = hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()
    return body, f"sha256={signature}"


@pytest.mark.asyncio
async def test_kb_webhook_updates_document_status_and_appends_event(
    route_client,
    db_session,
    monkeypatch,
) -> None:
    monkeypatch.setattr(settings, "KB_WEBHOOK_SECRET", "webhook-secret")
    document = await _document(db_session)
    payload = {
        "document_id": str(document.id),
        "stage": "pipeline",
        "status": "success",
        "metadata": {"task_id": "task-1"},
    }
    body, signature = _signed_body(payload, "webhook-secret")

    response = await route_client.client.post(
        "/api/v1/kb/webhook",
        content=body,
        headers={
            "Content-Type": "application/json",
            "X-KB-Signature": signature,
        },
    )

    assert response.status_code == 200
    assert response.json() == {"status": "ok", "document_status": "ready"}
    assert document.processing_status == "ready"

    events = await KBDocumentEventRepository(db_session).list_by_document(document.id)
    assert events[-1].event_type == "kb.pipeline.success"
    assert events[-1].event_metadata["task_id"] == "task-1"


@pytest.mark.asyncio
async def test_kb_webhook_rejects_missing_signature(
    route_client,
    db_session,
    monkeypatch,
) -> None:
    monkeypatch.setattr(settings, "KB_WEBHOOK_SECRET", "webhook-secret")
    document = await _document(db_session)

    response = await route_client.client.post(
        "/api/v1/kb/webhook",
        json={"document_id": str(document.id), "stage": "pipeline", "status": "success"},
        headers={"X-Request-ID": "req-webhook"},
    )

    assert response.status_code == 403
    assert response.json()["error"] == {
        "code": "FORBIDDEN",
        "message": "Missing KB webhook signature",
        "retryable": False,
        "details": {"request_id": "req-webhook"},
    }


@pytest.mark.asyncio
async def test_kb_webhook_rejects_invalid_signature(
    route_client,
    db_session,
    monkeypatch,
) -> None:
    monkeypatch.setattr(settings, "KB_WEBHOOK_SECRET", "webhook-secret")
    document = await _document(db_session)

    response = await route_client.client.post(
        "/api/v1/kb/webhook",
        json={"document_id": str(document.id), "stage": "pipeline", "status": "success"},
        headers={"X-KB-Signature": "sha256=bad"},
    )

    assert response.status_code == 403
    assert response.json()["error"]["message"] == "Invalid KB webhook signature"


@pytest.mark.asyncio
async def test_kb_webhook_rejects_stale_timestamp(
    route_client,
    db_session,
    monkeypatch,
) -> None:
    monkeypatch.setattr(settings, "KB_WEBHOOK_SECRET", "webhook-secret")
    document = await _document(db_session)
    payload = {
        "document_id": str(document.id),
        "stage": "pipeline",
        "status": "success",
        "timestamp": int(time.time()) - 1000,
    }
    body, signature = _signed_body(payload, "webhook-secret")

    response = await route_client.client.post(
        "/api/v1/kb/webhook",
        content=body,
        headers={
            "Content-Type": "application/json",
            "X-KB-Signature": signature,
        },
    )

    assert response.status_code == 403
    assert response.json()["error"]["message"] == "Stale KB webhook timestamp"
