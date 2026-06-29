"""Unit tests for KB webhook status mapping helpers."""

from __future__ import annotations

from types import SimpleNamespace
from uuid import uuid4

from app.services.kb_documents.status_mapping import (
    admin_kb_service_document_id,
    chunk_count_from_metadata,
    document_kb_service_document_id,
    map_kb_webhook_status,
    sanitize_failure_reason,
)


def test_map_kb_webhook_status_handles_terminal_processing_and_pending() -> None:
    assert map_kb_webhook_status("success", "pipeline") == "ready"
    assert map_kb_webhook_status("completed", None) == "ready"
    assert map_kb_webhook_status("success", "parse") == "processing"
    assert map_kb_webhook_status("SUCCESS", "chunk") == "processing"
    assert map_kb_webhook_status("success", "load_vector") == "processing"
    assert map_kb_webhook_status("failed", "pipeline") == "failed"
    assert map_kb_webhook_status("error", None) == "failed"
    assert map_kb_webhook_status("embedding", None) == "processing"
    assert map_kb_webhook_status("started", "embed") == "processing"
    assert map_kb_webhook_status("pending", None) == "uploaded"
    assert map_kb_webhook_status("unexpected", None) == "processing"


def test_chunk_count_from_metadata_accepts_only_non_negative_ints() -> None:
    assert chunk_count_from_metadata({"chunk_count": 0}) == 0
    assert chunk_count_from_metadata({"chunk_count": 42}) == 42
    assert chunk_count_from_metadata({"chunk_count": -1}) is None
    assert chunk_count_from_metadata({"chunk_count": True}) is None
    assert chunk_count_from_metadata({"chunk_count": "42"}) is None
    assert chunk_count_from_metadata({}) is None


def test_admin_kb_service_document_id_uses_payload_identity_rules() -> None:
    kb_document_id = uuid4()
    explicit_payload = SimpleNamespace(
        kb_service_document_id=kb_document_id,
        source_type=None,
        playbook_document_id=None,
        document_id=uuid4(),
    )
    assert admin_kb_service_document_id(explicit_payload) == kb_document_id

    document_id = uuid4()
    admin_payload = SimpleNamespace(
        kb_service_document_id=None,
        source_type="admin_upload",
        playbook_document_id=uuid4(),
        document_id=document_id,
    )
    assert admin_kb_service_document_id(admin_payload) == document_id

    conversation_payload = SimpleNamespace(
        kb_service_document_id=None,
        source_type="conversation_file",
        playbook_document_id=None,
        document_id=uuid4(),
    )
    assert admin_kb_service_document_id(conversation_payload) is None


def test_document_kb_service_document_id_returns_safe_string_or_none() -> None:
    kb_document_id = uuid4()

    assert (
        document_kb_service_document_id(
            SimpleNamespace(kb_service_document_id=kb_document_id)
        )
        == str(kb_document_id)
    )
    assert document_kb_service_document_id(SimpleNamespace()) is None
    assert document_kb_service_document_id(SimpleNamespace(kb_service_document_id=None)) is None


def test_sanitize_failure_reason_redacts_signed_urls_and_bounds_messages() -> None:
    assert sanitize_failure_reason(None) is None
    assert (
        sanitize_failure_reason(
            "Could not parse https://storage.example/file.pdf?signature=secret"
        )
        == "KB ingestion failed"
    )

    long_message = "x" * 600
    sanitized = sanitize_failure_reason(long_message)
    assert sanitized == "x" * 500
