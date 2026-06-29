"""Route-level tests for signed KB service webhook handling."""

from __future__ import annotations

import hashlib
import hmac
import json
import time
from uuid import uuid4

import pytest

from app.repositories.conversations import (
    ConversationFileRepository,
    ConversationRepository,
)
from app.repositories.identity import OrganizationRepository, UserRepository
from app.repositories.knowledge_base import (
    KBDocumentEventRepository,
    KBDocumentRepository,
)


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
    test_settings,
) -> None:
    monkeypatch.setattr(test_settings, "KB_WEBHOOK_SECRET", "webhook-secret")
    document = await _document(db_session)
    kb_service_document_id = uuid4()
    payload = {
        "document_id": str(document.id),
        "kb_service_document_id": str(kb_service_document_id),
        "source_type": "admin_upload",
        "playbook_document_id": str(document.id),
        "stage": "pipeline",
        "status": "success",
        "summary": "NIL handbook orientation summary.",
        "metadata": {"task_id": "task-1", "chunk_count": 42},
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
    assert document.kb_service_document_id == kb_service_document_id
    assert document.summary == "NIL handbook orientation summary."
    assert document.chunk_count == 42

    events = await KBDocumentEventRepository(db_session).list_by_document(document.id)
    assert events[-1].event_type == "kb.pipeline.success"
    assert events[-1].event_metadata["task_id"] == "task-1"
    assert events[-1].event_metadata["chunk_count"] == 42


@pytest.mark.asyncio
async def test_kb_webhook_does_not_regress_ready_document_on_late_stage_success(
    route_client,
    db_session,
    monkeypatch,
    test_settings,
) -> None:
    monkeypatch.setattr(test_settings, "KB_WEBHOOK_SECRET", "webhook-secret")
    document = await _document(db_session)
    kb_service_document_id = uuid4()
    ready_payload = {
        "document_id": str(document.id),
        "kb_service_document_id": str(kb_service_document_id),
        "source_type": "admin_upload",
        "playbook_document_id": str(document.id),
        "stage": "pipeline",
        "status": "success",
        "summary": "NIL handbook orientation summary.",
        "metadata": {"chunk_count": 42},
    }
    ready_body, ready_signature = _signed_body(ready_payload, "webhook-secret")
    late_payload = {
        **ready_payload,
        "stage": "load_vector",
        "status": "SUCCESS",
        "metadata": {"chunk_count": 42},
    }
    late_body, late_signature = _signed_body(late_payload, "webhook-secret")

    ready_response = await route_client.client.post(
        "/api/v1/kb/webhook",
        content=ready_body,
        headers={
            "Content-Type": "application/json",
            "X-KB-Signature": ready_signature,
        },
    )
    late_response = await route_client.client.post(
        "/api/v1/kb/webhook",
        content=late_body,
        headers={
            "Content-Type": "application/json",
            "X-KB-Signature": late_signature,
        },
    )

    assert ready_response.status_code == 200
    assert late_response.status_code == 200
    assert late_response.json() == {"status": "ok", "document_status": "ready"}
    assert document.processing_status == "ready"
    assert document.summary == "NIL handbook orientation summary."
    assert document.chunk_count == 42


@pytest.mark.asyncio
async def test_kb_webhook_mirrors_conversation_file_status_summary_and_counts(
    route_client,
    db_session,
    monkeypatch,
    test_settings,
) -> None:
    monkeypatch.setattr(test_settings, "KB_WEBHOOK_SECRET", "webhook-secret")
    organization = await OrganizationRepository(db_session).create(
        name="Playbook Athletics",
        slug="playbook-files",
    )
    athlete = await UserRepository(db_session).create(
        organization_id=organization.id,
        email="athlete@example.com",
        name="Jordan Athlete",
        auth_provider="google",
        provider_subject="athlete-file-subject",
    )
    conversation = await ConversationRepository(db_session).create(
        organization_id=organization.id,
        athlete_id=athlete.id,
    )
    file = await ConversationFileRepository(db_session).create(
        conversation_id=conversation.id,
        uploaded_by=athlete.id,
        filename="contract.pdf",
        content_type="application/pdf",
        size_bytes=123,
        storage_key="conversation-files/originals/contract.pdf",
        extraction_status="extracting",
    )
    kb_service_document_id = uuid4()
    payload = {
        "document_id": str(kb_service_document_id),
        "kb_service_document_id": str(kb_service_document_id),
        "source_type": "conversation_file",
        "conversation_id": str(conversation.id),
        "conversation_file_id": str(file.id),
        "stage": "pipeline",
        "status": "success",
        "summary": "Contract orientation summary.",
        "metadata": {
            "chunk_count": 7,
            "source_uri": "https://storage.example/contract.pdf?signature=secret",
            "raw_text": "private contract text",
            "model_input": "private summary prompt",
        },
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
    assert file.extraction_status == "ready"
    assert file.kb_service_document_id == kb_service_document_id
    assert file.summary == "Contract orientation summary."
    assert file.chunk_count == 7

    route_client.authenticate_as(athlete)
    detail_response = await route_client.client.get(
        f"/api/v1/conversations/{conversation.id}"
    )
    assert detail_response.status_code == 200
    file_summary = detail_response.json()["files"][0]
    assert file_summary["id"] == str(file.id)
    assert file_summary["extraction_status"] == "ready"
    assert file_summary["chunk_count"] == 7
    assert "summary" not in file_summary
    assert "storage_key" not in file_summary
    assert "source_uri" not in file_summary
    assert "raw_text" not in response.text
    assert "private summary prompt" not in response.text
    assert "signature=secret" not in response.text


@pytest.mark.asyncio
async def test_kb_webhook_marks_conversation_file_failed_with_sanitized_error(
    route_client,
    db_session,
    monkeypatch,
    test_settings,
) -> None:
    monkeypatch.setattr(test_settings, "KB_WEBHOOK_SECRET", "webhook-secret")
    organization = await OrganizationRepository(db_session).create(
        name="Playbook Athletics",
        slug="playbook-file-failure",
    )
    athlete = await UserRepository(db_session).create(
        organization_id=organization.id,
        email="athlete-fail@example.com",
        name="Jordan Athlete",
        auth_provider="google",
        provider_subject="athlete-file-fail-subject",
    )
    conversation = await ConversationRepository(db_session).create(
        organization_id=organization.id,
        athlete_id=athlete.id,
    )
    file = await ConversationFileRepository(db_session).create(
        conversation_id=conversation.id,
        uploaded_by=athlete.id,
        filename="contract.pdf",
        content_type="application/pdf",
        size_bytes=123,
        storage_key="conversation-files/originals/contract.pdf",
        extraction_status="extracting",
    )
    payload = {
        "document_id": str(uuid4()),
        "source_type": "conversation_file",
        "conversation_id": str(conversation.id),
        "conversation_file_id": str(file.id),
        "stage": "pipeline",
        "status": "failed",
        "error_message": (
            "Could not parse https://storage.example/contract.pdf?signature=secret"
        ),
        "metadata": {
            "signed_url": "https://storage.example/contract.pdf?signature=secret",
            "file_contents": "private contract text",
            "model_inputs": ["private model batch"],
        },
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
    assert response.json()["document_status"] == "failed"
    assert file.extraction_status == "failed"
    assert file.error_message is not None
    assert "storage.example" not in file.error_message
    assert "signature=secret" not in file.error_message
    assert "private contract text" not in response.text
    assert "private model batch" not in response.text


@pytest.mark.asyncio
async def test_kb_webhook_rejects_conversation_file_scope_mismatch(
    route_client,
    db_session,
    monkeypatch,
    test_settings,
) -> None:
    monkeypatch.setattr(test_settings, "KB_WEBHOOK_SECRET", "webhook-secret")
    organization = await OrganizationRepository(db_session).create(
        name="Playbook Athletics",
        slug="playbook-file-mismatch",
    )
    athlete = await UserRepository(db_session).create(
        organization_id=organization.id,
        email="athlete-mismatch@example.com",
        name="Jordan Athlete",
        auth_provider="google",
        provider_subject="athlete-file-mismatch-subject",
    )
    conversation = await ConversationRepository(db_session).create(
        organization_id=organization.id,
        athlete_id=athlete.id,
    )
    other_conversation = await ConversationRepository(db_session).create(
        organization_id=organization.id,
        athlete_id=athlete.id,
    )
    file = await ConversationFileRepository(db_session).create(
        conversation_id=conversation.id,
        uploaded_by=athlete.id,
        filename="contract.pdf",
        content_type="application/pdf",
        size_bytes=123,
        storage_key="conversation-files/originals/contract.pdf",
        extraction_status="extracting",
    )
    payload = {
        "document_id": str(uuid4()),
        "source_type": "conversation_file",
        "conversation_id": str(other_conversation.id),
        "conversation_file_id": str(file.id),
        "stage": "pipeline",
        "status": "success",
        "summary": "Wrong conversation summary.",
        "metadata": {"chunk_count": 7},
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

    assert response.status_code == 404
    assert file.extraction_status == "extracting"
    assert file.chunk_count == 0
    assert file.summary is None


@pytest.mark.asyncio
async def test_kb_webhook_rejects_missing_signature(
    route_client,
    db_session,
    monkeypatch,
    test_settings,
) -> None:
    monkeypatch.setattr(test_settings, "KB_WEBHOOK_SECRET", "webhook-secret")
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
    test_settings,
) -> None:
    monkeypatch.setattr(test_settings, "KB_WEBHOOK_SECRET", "webhook-secret")
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
    test_settings,
) -> None:
    monkeypatch.setattr(test_settings, "KB_WEBHOOK_SECRET", "webhook-secret")
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
