"""Phase 3 KB ingestion/retrieval end-to-end smoke test.

This is local-development tooling. It validates the full Phase 3 path through
the public backend API, the local KB provider, kb-service ingestion/webhooks,
and athlete chat streaming without introducing test-only product endpoints.
"""

from __future__ import annotations

import argparse
import asyncio
import html
import io
import json
import re
import sys
import time
import zipfile
from collections.abc import Iterable, Iterator
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from uuid import UUID

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

import httpx  # noqa: E402

from app.core.config import Settings, get_settings  # noqa: E402
from app.infrastructure.db.session import (  # noqa: E402
    cleanup_db_engine,
    get_session_factory,
)
from app.infrastructure.knowledgebase.providers.local_kb import (  # noqa: E402
    LocalKBProvider,
)
from app.repositories.knowledge_base import (  # noqa: E402
    KBDocumentEventRepository,
    KBDocumentRepository,
)
from scripts.phase1_dev_auth import seed_phase1_users  # noqa: E402

DOCX_CONTENT_TYPE = (
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
)
WORD_DOCUMENT_CONTENT_TYPE = (
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"
)
SMOKE_DOC_TITLE = "Phase 3 KB E2E NIL Disclosure Smoke"
SMOKE_DOC_FILENAME = "phase3-kb-e2e-nil-disclosure.docx"
SMOKE_DOC_TEXT = (
    "Phase 3 smoke policy. Athletes must disclose NIL brand partnership deals "
    "before signing. Compliance review is required before agreements are finalized."
)
SMOKE_QUERY = (
    "What does the Phase 3 smoke policy require before an athlete signs a NIL "
    "brand partnership deal?"
)
FAILED_DOC_TITLE = "Phase 3 KB E2E Malformed Smoke"
FAILED_DOC_FILENAME = "phase3-kb-e2e-malformed.docx"
SAFE_MATCH_SUMMARY = "NIL disclosure compliance phrase"
TERMINAL_EVENTS = {"complete", "error"}
EXPECTED_AUDIT_ACTIONS = {
    "kb.document_upload_requested",
    "kb.document_uploaded",
    "kb.document_retry_requested",
    "kb.document_deleted",
}
EXPECTED_DOCUMENT_EVENTS = {
    "document.upload_requested",
    "document.uploaded",
    "ingestion.queued",
}
SENSITIVE_QUERY_KEYS = (
    "X-Amz-Credential",
    "X-Amz-Security-Token",
    "X-Amz-Signature",
    "AWSAccessKeyId",
    "Signature",
    "token",
    "access_token",
    "authorization",
    "credential",
    "signature",
)


class SmokeTestError(RuntimeError):
    """Raised when the Phase 3 smoke test cannot prove an invariant."""


@dataclass(frozen=True)
class SSEEvent:
    """Parsed server-sent event payload."""

    stream_id: str | None
    event: str
    data: Any
    payload: Any


@dataclass(frozen=True)
class SmokeTokens:
    """Seeded principals needed by the live smoke."""

    admin_token: str
    athlete_token: str
    super_token: str
    organization_id: UUID


@dataclass(frozen=True)
class SmokeArgs:
    """Resolved CLI arguments."""

    backend_url: str
    kb_url: str
    timeout_seconds: float
    poll_interval_seconds: float
    keep: bool


def _create_docx_bytes(*, title: str, paragraphs: list[str]) -> bytes:
    """Create a minimal DOCX package using stdlib zipfile only."""
    body = "\n".join(
        f"<w:p><w:r><w:t>{html.escape(paragraph)}</w:t></w:r></w:p>"
        for paragraph in [title, *paragraphs]
    )
    escaped_title = html.escape(title)
    document_xml = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">'
        f"<w:body>{body}<w:sectPr/></w:body>"
        "</w:document>"
    )
    content_types = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
        '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
        '<Default Extension="xml" ContentType="application/xml"/>'
        f'<Override PartName="/word/document.xml" ContentType="{WORD_DOCUMENT_CONTENT_TYPE}"/>'
        '<Override PartName="/docProps/core.xml" ContentType="application/vnd.openxmlformats-package.core-properties+xml"/>'
        '<Override PartName="/docProps/app.xml" ContentType="application/vnd.openxmlformats-officedocument.extended-properties+xml"/>'
        "</Types>"
    )
    rels = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
        '<Relationship Id="rId1" '
        'Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" '
        'Target="word/document.xml"/>'
        '<Relationship Id="rId2" '
        'Type="http://schemas.openxmlformats.org/package/2006/relationships/metadata/core-properties" '
        'Target="docProps/core.xml"/>'
        '<Relationship Id="rId3" '
        'Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/extended-properties" '
        'Target="docProps/app.xml"/>'
        "</Relationships>"
    )
    core = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<cp:coreProperties '
        'xmlns:cp="http://schemas.openxmlformats.org/package/2006/metadata/core-properties" '
        'xmlns:dc="http://purl.org/dc/elements/1.1/" '
        'xmlns:dcterms="http://purl.org/dc/terms/" '
        'xmlns:dcmitype="http://purl.org/dc/dcmitype/" '
        'xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance">'
        f"<dc:title>{escaped_title}</dc:title>"
        "</cp:coreProperties>"
    )
    app = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<Properties xmlns="http://schemas.openxmlformats.org/officeDocument/2006/extended-properties" '
        'xmlns:vt="http://schemas.openxmlformats.org/officeDocument/2006/docPropsVTypes">'
        "<Application>Playbook Phase 3 Smoke</Application>"
        "</Properties>"
    )

    payload = io.BytesIO()
    with zipfile.ZipFile(payload, mode="w", compression=zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("[Content_Types].xml", content_types)
        archive.writestr("_rels/.rels", rels)
        archive.writestr("word/document.xml", document_xml)
        archive.writestr("docProps/core.xml", core)
        archive.writestr("docProps/app.xml", app)
    return payload.getvalue()


def _build_upload_form(
    *,
    fields: dict[str, str],
    filename: str,
    content_type: str,
    payload: bytes,
) -> tuple[dict[str, str], dict[str, tuple[str, bytes, str]]]:
    """Build a safe, replayable multipart form for presigned POST uploads."""
    return dict(fields), {"file": (filename, payload, content_type)}


def _iter_sse_events(lines: Iterable[str]) -> Iterator[SSEEvent]:
    """Parse server-sent event lines into structured events."""
    frame: list[str] = []
    for raw_line in lines:
        line = raw_line.rstrip("\r\n")
        if line == "":
            if frame:
                yield _parse_sse_frame(frame)
                frame = []
            continue
        frame.append(line)
    if frame:
        yield _parse_sse_frame(frame)


def _terminal_success_event(events: Iterable[SSEEvent]) -> SSEEvent:
    """Return the complete event or raise on stream error / missing terminal."""
    for event in events:
        if event.event == "error":
            message = _event_error_message(event)
            raise SmokeTestError(f"athlete chat stream failed: {message}")
        if event.event == "complete":
            return event
    raise SmokeTestError("athlete chat stream ended without a complete event")


def _redact_sensitive(value: str) -> str:
    """Remove tokens and signed URL query details from diagnostic text."""
    redacted = re.sub(
        r"Bearer\s+[A-Za-z0-9._~+/=-]+",
        "Bearer [redacted]",
        value,
        flags=re.IGNORECASE,
    )
    for key in SENSITIVE_QUERY_KEYS:
        redacted = re.sub(
            rf"({re.escape(key)}=)[^&\s\"']+",
            r"\1[redacted]",
            redacted,
            flags=re.IGNORECASE,
        )
    return redacted


def _safe_response_detail(response: httpx.Response, *, limit: int = 500) -> str:
    """Return a redacted bounded error payload for CLI diagnostics."""
    try:
        detail = json.dumps(response.json(), sort_keys=True, default=str)
    except ValueError:
        detail = response.text
    redacted = _redact_sensitive(detail)
    if len(redacted) > limit:
        return redacted[:limit] + "..."
    return redacted


async def _run(args: SmokeArgs) -> None:
    settings = get_settings()
    tokens = await _seed_tokens(settings)
    timeout = httpx.Timeout(args.timeout_seconds)
    document_id: str | None = None
    failed_document_id: str | None = None

    async with httpx.AsyncClient(
        base_url=args.backend_url.rstrip("/"),
        timeout=timeout,
    ) as client:
        admin_headers = _auth_headers(tokens.admin_token)
        athlete_headers = _auth_headers(tokens.athlete_token)
        super_headers = _auth_headers(tokens.super_token)

        await _assert_health(client, args.kb_url)
        _emit("Seeded local admin, athlete, and super-admin principals.")

        try:
            upload = await _upload_admin_docx(
                client,
                headers=admin_headers,
                title=SMOKE_DOC_TITLE,
                filename=SMOKE_DOC_FILENAME,
                payload=_create_docx_bytes(
                    title=SMOKE_DOC_TITLE,
                    paragraphs=[SMOKE_DOC_TEXT],
                ),
            )
            document_id = upload["document"]["id"]
            upload_request_id = upload["upload"]["upload_request_id"]
            await _complete_upload(
                client,
                headers=admin_headers,
                document_id=document_id,
                upload_request_id=upload_request_id,
            )
            ready_document = await _wait_for_document_status(
                client,
                headers=admin_headers,
                document_id=document_id,
                terminal_statuses={"ready"},
                timeout_seconds=args.timeout_seconds,
                poll_interval_seconds=args.poll_interval_seconds,
            )
            _assert_ready_document(ready_document)
            await _assert_backend_mirror(document_id)
            await _assert_document_events(document_id)
            await _assert_audit_actions(
                client,
                headers=super_headers,
                document_id=document_id,
                actions=EXPECTED_AUDIT_ACTIONS
                - {"kb.document_deleted", "kb.document_retry_requested"},
            )
            _emit("Ready admin document mirrored kb-service metadata.")

            await _assert_provider_search(
                settings,
                organization_id=tokens.organization_id,
                expected_document_id=document_id,
                should_find=True,
            )
            _emit(f"LocalKBProvider returned the smoke chunk ({SAFE_MATCH_SUMMARY}).")

            await _assert_athlete_chat_citation(
                client,
                headers=athlete_headers,
                document_id=document_id,
                timeout_seconds=args.timeout_seconds,
            )
            _emit("Athlete chat stream completed with a persisted KB citation.")

            failed_upload = await _upload_admin_docx(
                client,
                headers=admin_headers,
                title=FAILED_DOC_TITLE,
                filename=FAILED_DOC_FILENAME,
                payload=b"not-a-valid-docx-package",
            )
            failed_document_id = failed_upload["document"]["id"]
            await _complete_upload(
                client,
                headers=admin_headers,
                document_id=failed_document_id,
                upload_request_id=failed_upload["upload"]["upload_request_id"],
            )
            failed_document = await _wait_for_document_status(
                client,
                headers=admin_headers,
                document_id=failed_document_id,
                terminal_statuses={"failed"},
                timeout_seconds=args.timeout_seconds,
                poll_interval_seconds=args.poll_interval_seconds,
            )
            if not failed_document.get("failure_reason"):
                raise SmokeTestError("malformed document failed without a failure_reason")
            await _assert_provider_search(
                settings,
                organization_id=tokens.organization_id,
                expected_document_id=failed_document_id,
                should_find=False,
            )
            _emit("Malformed document failed and did not contribute retrieval results.")

            await _retry_document(
                client,
                headers=admin_headers,
                document_id=document_id,
            )
            retried = await _wait_for_document_status(
                client,
                headers=admin_headers,
                document_id=document_id,
                terminal_statuses={"ready"},
                timeout_seconds=args.timeout_seconds,
                poll_interval_seconds=args.poll_interval_seconds,
            )
            _assert_ready_document(retried)
            await _assert_backend_mirror(document_id)
            _emit("Retry reprocessed the linked document back to ready.")

            await _delete_document(client, headers=admin_headers, document_id=document_id)
            document_id = None
            await _assert_document_deleted(client, headers=admin_headers, document_id=retried["id"])
            await _assert_provider_search(
                settings,
                organization_id=tokens.organization_id,
                expected_document_id=retried["id"],
                should_find=False,
            )
            await _assert_audit_actions(
                client,
                headers=super_headers,
                document_id=retried["id"],
                actions=EXPECTED_AUDIT_ACTIONS,
            )
            _emit("Delete removed the backend document and searchable KB result.")
        finally:
            if not args.keep:
                if document_id is not None:
                    await _delete_document_quietly(
                        client,
                        headers=admin_headers,
                        document_id=document_id,
                    )
                if failed_document_id is not None:
                    await _delete_document_quietly(
                        client,
                        headers=admin_headers,
                        document_id=failed_document_id,
                    )


async def _seed_tokens(settings: Settings) -> SmokeTokens:
    async with get_session_factory(settings)() as session:
        seeded = await seed_phase1_users(session, settings)
    await cleanup_db_engine()
    return SmokeTokens(
        admin_token=seeded["admin"].token,
        athlete_token=seeded["athlete"].token,
        super_token=seeded["super_admin"].token,
        organization_id=seeded["admin"].organization_id,
    )


async def _assert_health(client: httpx.AsyncClient, kb_url: str) -> None:
    backend = await client.get("/api/v1/health")
    if backend.status_code != 200:
        raise SmokeTestError(
            f"backend health check failed: {_safe_response_detail(backend)}"
        )
    kb_health = await client.get(kb_url.rstrip("/") + "/health")
    if kb_health.status_code != 200:
        raise SmokeTestError(
            f"kb-service health check failed: {_safe_response_detail(kb_health)}"
        )


async def _upload_admin_docx(
    client: httpx.AsyncClient,
    *,
    headers: dict[str, str],
    title: str,
    filename: str,
    payload: bytes,
) -> dict[str, Any]:
    request = {
        "filename": filename,
        "content_type": DOCX_CONTENT_TYPE,
        "size_bytes": len(payload),
        "title": title,
        "metadata_tags": {
            "phase": "phase-3",
            "smoke": "kb-ingestion-retrieval",
        },
    }
    upload = await _request_json(
        client,
        "POST",
        "/api/v1/admin/kb/documents",
        expected_statuses={201},
        headers=headers,
        json_body=request,
    )
    data, files = _build_upload_form(
        fields=upload["upload"]["fields"],
        filename=filename,
        content_type=DOCX_CONTENT_TYPE,
        payload=payload,
    )
    storage_response = await client.post(
        upload["upload"]["url"],
        data=data,
        files=files,
    )
    if storage_response.status_code not in {200, 201, 204}:
        raise SmokeTestError(
            "direct storage upload failed: "
            f"{_safe_response_detail(storage_response)}"
        )
    return upload


async def _complete_upload(
    client: httpx.AsyncClient,
    *,
    headers: dict[str, str],
    document_id: str,
    upload_request_id: str,
) -> dict[str, Any]:
    return await _request_json(
        client,
        "POST",
        f"/api/v1/admin/kb/documents/{document_id}/upload-complete",
        expected_statuses={200},
        headers=headers,
        json_body={"upload_request_id": upload_request_id},
    )


async def _wait_for_document_status(
    client: httpx.AsyncClient,
    *,
    headers: dict[str, str],
    document_id: str,
    terminal_statuses: set[str],
    timeout_seconds: float,
    poll_interval_seconds: float,
) -> dict[str, Any]:
    deadline = time.monotonic() + timeout_seconds
    last_document: dict[str, Any] | None = None
    while time.monotonic() < deadline:
        document = await _request_json(
            client,
            "GET",
            f"/api/v1/admin/kb/documents/{document_id}",
            expected_statuses={200},
            headers=headers,
        )
        last_document = document
        status = str(document.get("processing_status"))
        if status in terminal_statuses:
            return document
        if status == "failed" and "failed" not in terminal_statuses:
            reason = document.get("failure_reason") or "unknown failure"
            raise SmokeTestError(f"document {document_id} failed: {reason}")
        await asyncio.sleep(poll_interval_seconds)

    last_status = (last_document or {}).get("processing_status", "unknown")
    expected = ", ".join(sorted(terminal_statuses))
    raise SmokeTestError(
        f"document {document_id} did not reach {expected}; last status={last_status}"
    )


def _assert_ready_document(document: dict[str, Any]) -> None:
    if document.get("processing_status") != "ready":
        raise SmokeTestError("ready document assertion received a non-ready document")
    if not document.get("kb_service_document_id"):
        raise SmokeTestError("ready document is missing kb_service_document_id")
    tags = document.get("metadata_tags") or {}
    if tags.get("phase") != "phase-3":
        raise SmokeTestError("ready document is missing smoke metadata tags")


async def _assert_document_events(document_id: str) -> None:
    settings = get_settings()
    async with get_session_factory(settings)() as session:
        events = await KBDocumentEventRepository(session).list_by_document(
            UUID(document_id)
        )
    await cleanup_db_engine()
    event_types = {event.event_type for event in events}
    missing = EXPECTED_DOCUMENT_EVENTS - event_types
    if missing:
        raise SmokeTestError(
            "document lifecycle events missing: " + ", ".join(sorted(missing))
        )


async def _assert_backend_mirror(document_id: str) -> None:
    settings = get_settings()
    async with get_session_factory(settings)() as session:
        document = await KBDocumentRepository(session).get(UUID(document_id))
        if document is None:
            raise SmokeTestError("backend document mirror row was not found")
        kb_service_document_id = document.kb_service_document_id
        summary = document.summary
        chunk_count = document.chunk_count
    await cleanup_db_engine()
    if kb_service_document_id is None:
        raise SmokeTestError("backend mirror is missing kb_service_document_id")
    if not summary:
        raise SmokeTestError("backend mirror is missing kb-service summary")
    if chunk_count <= 0:
        raise SmokeTestError("backend mirror is missing kb-service chunk_count")


async def _assert_audit_actions(
    client: httpx.AsyncClient,
    *,
    headers: dict[str, str],
    document_id: str,
    actions: set[str],
) -> None:
    audit_logs = await _request_json(
        client,
        "GET",
        "/api/v1/admin/audit-logs",
        expected_statuses={200},
        headers=headers,
        params={"target_type": "kb_document", "target_id": document_id},
    )
    observed = {log["action"] for log in audit_logs}
    missing = actions - observed
    if missing:
        raise SmokeTestError("audit actions missing: " + ", ".join(sorted(missing)))


async def _assert_provider_search(
    settings: Settings,
    *,
    organization_id: UUID,
    expected_document_id: str,
    should_find: bool,
) -> None:
    provider = LocalKBProvider(settings)
    try:
        result = await provider.search_admin_uploads(
            query=SMOKE_QUERY,
            organization_id=organization_id,
            max_docs=5,
            score_threshold=0.0,
            metadata_filter={"visibility_policy": {"scope": "all_athletes"}},
        )
    finally:
        await provider.close()

    matches = [
        source
        for source in result.sources
        if str(
            source.metadata.get("playbook_document_id")
            or source.metadata.get("document_id")
        )
        == expected_document_id
    ]
    if should_find:
        if not matches:
            raise SmokeTestError("expected smoke document was not returned by provider")
        source = matches[0]
        lowered = source.text.lower()
        if not all(term in lowered for term in ("nil", "disclose", "compliance")):
            raise SmokeTestError("provider result did not contain the smoke terms")
        metadata = source.metadata
        for key in (
            "kb_service_document_id",
            "chunk_id",
            "chunk_index",
            "source_title",
        ):
            if metadata.get(key) in (None, ""):
                raise SmokeTestError(f"provider result missing citation metadata: {key}")
        return

    if matches:
        raise SmokeTestError("unexpected searchable result remained after failure/delete")


async def _assert_athlete_chat_citation(
    client: httpx.AsyncClient,
    *,
    headers: dict[str, str],
    document_id: str,
    timeout_seconds: float,
) -> None:
    start_response = await _request_json(
        client,
        "POST",
        "/api/v1/conversations",
        expected_statuses={202},
        headers=headers,
        json_body={"content": SMOKE_QUERY},
    )
    conversation_id = start_response["conversation"]["id"]
    assistant_message_id = start_response["assistant_message_id"]
    stream_url = start_response["stream_url"]
    task_id = start_response["task_id"]
    stream_path = _stream_path(stream_url, task_id=task_id)

    events = await _consume_stream(
        client,
        stream_path=stream_path,
        headers=headers,
        timeout_seconds=timeout_seconds,
    )
    terminal = _terminal_success_event(events)
    if (terminal.data or {}).get("answer_type") != "grounded_answer":
        raise SmokeTestError("athlete chat did not produce a grounded answer")

    detail = await _request_json(
        client,
        "GET",
        f"/api/v1/conversations/{conversation_id}",
        expected_statuses={200},
        headers=headers,
    )
    assistant = next(
        (
            message
            for message in detail.get("messages", [])
            if message.get("id") == assistant_message_id
        ),
        None,
    )
    if assistant is None:
        raise SmokeTestError("assistant message was not returned by conversation detail")
    if assistant.get("status") != "complete":
        raise SmokeTestError("assistant message was not persisted as complete")
    if assistant.get("metadata", {}).get("answer_type") != "grounded_answer":
        raise SmokeTestError("assistant message was not persisted as grounded")
    citations = assistant.get("citations", [])
    citation = next(
        (
            item
            for item in citations
            if str(item.get("document_id")) == document_id
            or str(item.get("source_metadata", {}).get("playbook_document_id"))
            == document_id
        ),
        None,
    )
    if citation is None:
        raise SmokeTestError("assistant message is missing the uploaded KB citation")
    if citation.get("source_title") != SMOKE_DOC_TITLE:
        raise SmokeTestError("persisted citation has the wrong source title")
    if not citation.get("chunk_id"):
        raise SmokeTestError("persisted citation is missing chunk_id")
    source_metadata = citation.get("source_metadata") or {}
    for key in ("kb_service_document_id", "chunk_index", "source_type"):
        if source_metadata.get(key) in (None, ""):
            raise SmokeTestError(f"persisted citation missing metadata: {key}")


async def _consume_stream(
    client: httpx.AsyncClient,
    *,
    stream_path: str,
    headers: dict[str, str],
    timeout_seconds: float,
) -> list[SSEEvent]:
    deadline = time.monotonic() + timeout_seconds
    events: list[SSEEvent] = []
    frame: list[str] = []
    async with client.stream("GET", stream_path, headers=headers) as response:
        if response.status_code != 200:
            raise SmokeTestError(
                f"stream request failed: {_safe_response_detail(response)}"
            )
        async for line in response.aiter_lines():
            if time.monotonic() > deadline:
                raise SmokeTestError("athlete chat stream timed out")
            if line == "":
                if frame:
                    event = next(_iter_sse_events([*frame, ""]))
                    events.append(event)
                    frame = []
                    if event.event in TERMINAL_EVENTS:
                        return events
                continue
            frame.append(line)
    return events


async def _retry_document(
    client: httpx.AsyncClient,
    *,
    headers: dict[str, str],
    document_id: str,
) -> None:
    await _request_json(
        client,
        "POST",
        f"/api/v1/admin/kb/documents/{document_id}/retry",
        expected_statuses={200},
        headers=headers,
    )


async def _delete_document(
    client: httpx.AsyncClient,
    *,
    headers: dict[str, str],
    document_id: str,
) -> None:
    await _request_no_content(
        client,
        "DELETE",
        f"/api/v1/admin/kb/documents/{document_id}",
        expected_statuses={204},
        headers=headers,
    )


async def _delete_document_quietly(
    client: httpx.AsyncClient,
    *,
    headers: dict[str, str],
    document_id: str,
) -> None:
    try:
        await _delete_document(client, headers=headers, document_id=document_id)
    except SmokeTestError as exc:
        _emit(f"Cleanup skipped for {document_id}: {_redact_sensitive(str(exc))}")


async def _assert_document_deleted(
    client: httpx.AsyncClient,
    *,
    headers: dict[str, str],
    document_id: str,
) -> None:
    response = await client.get(
        f"/api/v1/admin/kb/documents/{document_id}",
        headers=headers,
    )
    if response.status_code != 404:
        raise SmokeTestError(
            f"deleted document was still readable: {_safe_response_detail(response)}"
        )


async def _request_json(
    client: httpx.AsyncClient,
    method: str,
    path: str,
    *,
    expected_statuses: set[int],
    headers: dict[str, str],
    json_body: dict[str, Any] | None = None,
    params: dict[str, Any] | None = None,
) -> dict[str, Any] | list[Any]:
    response = await client.request(
        method,
        path,
        headers=headers,
        json=json_body,
        params=params,
    )
    if response.status_code not in expected_statuses:
        raise SmokeTestError(
            f"{method} {path} returned {response.status_code}: "
            f"{_safe_response_detail(response)}"
        )
    try:
        parsed = response.json()
    except ValueError as exc:
        raise SmokeTestError(f"{method} {path} did not return JSON") from exc
    if not isinstance(parsed, (dict, list)):
        raise SmokeTestError(f"{method} {path} returned an unexpected payload")
    return parsed


async def _request_no_content(
    client: httpx.AsyncClient,
    method: str,
    path: str,
    *,
    expected_statuses: set[int],
    headers: dict[str, str],
) -> None:
    response = await client.request(method, path, headers=headers)
    if response.status_code not in expected_statuses:
        raise SmokeTestError(
            f"{method} {path} returned {response.status_code}: "
            f"{_safe_response_detail(response)}"
        )


def _parse_sse_frame(frame: list[str]) -> SSEEvent:
    stream_id: str | None = None
    event_name: str | None = None
    data_lines: list[str] = []
    for line in frame:
        if line.startswith(":"):
            continue
        field, _, value = line.partition(":")
        if value.startswith(" "):
            value = value[1:]
        if field == "id":
            stream_id = value
        elif field == "event":
            event_name = value
        elif field == "data":
            data_lines.append(value)

    data_text = "\n".join(data_lines)
    payload: Any
    try:
        payload = json.loads(data_text) if data_text else {}
    except json.JSONDecodeError:
        payload = data_text
    nested_data = payload.get("data") if isinstance(payload, dict) else payload
    resolved_event = event_name
    if resolved_event is None and isinstance(payload, dict):
        resolved_event = str(payload.get("event_type") or "message")
    return SSEEvent(
        stream_id=stream_id,
        event=resolved_event or "message",
        data=nested_data,
        payload=payload,
    )


def _event_error_message(event: SSEEvent) -> str:
    data = event.data if isinstance(event.data, dict) else {}
    message = data.get("message") or data.get("error") or "unknown stream error"
    return _redact_sensitive(str(message))


def _stream_path(stream_url: str, *, task_id: str) -> str:
    if stream_url.startswith(("http://", "https://")):
        return stream_url
    separator = "&" if "?" in stream_url else "?"
    if "task_id=" in stream_url:
        return stream_url
    return f"{stream_url}{separator}task_id={task_id}"


def _auth_headers(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def _emit(message: str) -> None:
    sys.stdout.write(_redact_sensitive(message) + "\n")
    sys.stdout.flush()


def _parse_args(argv: list[str] | None = None) -> SmokeArgs:
    parser = argparse.ArgumentParser(
        description="Run the Phase 3 admin KB ingestion/retrieval smoke test.",
    )
    parser.add_argument("--backend-url", default="http://localhost:8000")
    parser.add_argument("--kb-url", default="http://localhost:8001")
    parser.add_argument("--timeout-seconds", type=float, default=300.0)
    parser.add_argument("--poll-interval-seconds", type=float, default=2.0)
    parser.add_argument(
        "--keep",
        action="store_true",
        help="Leave smoke documents in place for manual inspection.",
    )
    args = parser.parse_args(argv)
    return SmokeArgs(
        backend_url=args.backend_url,
        kb_url=args.kb_url,
        timeout_seconds=args.timeout_seconds,
        poll_interval_seconds=args.poll_interval_seconds,
        keep=args.keep,
    )


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv)
    try:
        asyncio.run(_run(args))
    except SmokeTestError as exc:
        sys.stderr.write("FAIL: " + _redact_sensitive(str(exc)) + "\n")
        return 1
    except httpx.HTTPError as exc:
        sys.stderr.write("FAIL: HTTP error: " + _redact_sensitive(str(exc)) + "\n")
        return 1
    _emit("PASS: Phase 3 KB ingestion/retrieval smoke completed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
