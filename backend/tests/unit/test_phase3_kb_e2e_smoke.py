from __future__ import annotations

import io
import zipfile

import httpx
import pytest

from scripts.phase3_kb_e2e_smoke import (
    DOCX_CONTENT_TYPE,
    WORD_DOCUMENT_CONTENT_TYPE,
    SmokeTestError,
    _build_upload_form,
    _create_docx_bytes,
    _iter_sse_events,
    _redact_sensitive,
    _safe_response_detail,
    _terminal_success_event,
)


def test_create_docx_bytes_writes_minimal_word_document() -> None:
    payload = _create_docx_bytes(
        title="NIL <Smoke>",
        paragraphs=["Athletes disclose NIL terms before signing."],
    )

    with zipfile.ZipFile(io.BytesIO(payload)) as archive:
        names = set(archive.namelist())
        document_xml = archive.read("word/document.xml").decode()
        content_types = archive.read("[Content_Types].xml").decode()

    assert "word/document.xml" in names
    assert WORD_DOCUMENT_CONTENT_TYPE in content_types
    assert "NIL &lt;Smoke&gt;" in document_xml
    assert "Athletes disclose NIL terms before signing." in document_xml


def test_iter_sse_events_parses_named_event_payloads() -> None:
    lines = [
        "id: 1700000000000-0",
        "event: chunk",
        'data: {"data": {"delta": "hello"}}',
        "",
        "id: 1700000000001-0",
        "event: complete",
        'data: {"data": {"status": "complete"}}',
        "",
    ]

    events = list(_iter_sse_events(lines))

    assert [event.event for event in events] == ["chunk", "complete"]
    assert events[0].data == {"delta": "hello"}
    assert events[1].stream_id == "1700000000001-0"


def test_terminal_success_event_rejects_stream_errors() -> None:
    lines = [
        "event: error",
        'data: {"data": {"message": "model failed", "token": "secret-token"}}',
        "",
    ]

    with pytest.raises(SmokeTestError, match="model failed"):
        _terminal_success_event(_iter_sse_events(lines))


def test_redact_sensitive_removes_tokens_and_signed_url_details() -> None:
    value = (
        "Authorization: Bearer abc.def.ghi "
        "url=http://localhost:9000/bucket/key?X-Amz-Signature=abcdef&token=raw-token"
    )

    redacted = _redact_sensitive(value)

    assert "abc.def.ghi" not in redacted
    assert "abcdef" not in redacted
    assert "raw-token" not in redacted
    assert "[redacted]" in redacted


def test_safe_response_detail_redacts_and_truncates() -> None:
    response = httpx.Response(
        500,
        json={"detail": "Bearer super-secret-token " + ("x" * 400)},
        request=httpx.Request("GET", "http://backend.local/api/v1/test"),
    )

    detail = _safe_response_detail(response, limit=120)

    assert "super-secret-token" not in detail
    assert detail.endswith("...")
    assert len(detail) <= 123


def test_build_upload_form_preserves_fields_and_file_tuple() -> None:
    data, files = _build_upload_form(
        fields={"key": "kb/originals/doc.docx", "Content-Type": DOCX_CONTENT_TYPE},
        filename="doc.docx",
        content_type=DOCX_CONTENT_TYPE,
        payload=b"docx-bytes",
    )

    assert data == {"key": "kb/originals/doc.docx", "Content-Type": DOCX_CONTENT_TYPE}
    assert files == {"file": ("doc.docx", b"docx-bytes", DOCX_CONTENT_TYPE)}
