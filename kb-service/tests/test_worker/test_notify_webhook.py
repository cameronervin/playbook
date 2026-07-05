from __future__ import annotations

import httpx
from structlog.testing import capture_logs

from app.core.log_redaction import redact_event_dict
from app.workers.tasks import notify


def test_webhook_url_from_metadata_skips_when_disabled() -> None:
    assert (
        notify._webhook_url_from_metadata(
            {"webhook_enabled": False, "status_webhook_url": None},
            fallback_base_url="http://backend.test",
        )
        is None
    )


def test_webhook_url_from_metadata_uses_stored_url_when_enabled() -> None:
    assert notify._webhook_url_from_metadata(
        {
            "webhook_enabled": True,
            "status_webhook_url": "http://backend.test/api/v1/kb/webhook",
        },
        fallback_base_url="http://fallback.test",
    ) == "http://backend.test/api/v1/kb/webhook"


def test_webhook_url_from_metadata_falls_back_for_legacy_documents() -> None:
    assert notify._webhook_url_from_metadata(
        {"source_title": "Legacy document"},
        fallback_base_url="http://backend.test",
    ) == "http://backend.test/api/v1/kb/webhook"


def test_notify_status_task_skips_http_post_without_webhook_url(monkeypatch) -> None:
    def fail_post(*args, **kwargs):
        raise AssertionError("httpx.post should not be called when webhook is disabled")

    monkeypatch.setattr(notify, "_load_webhook_url", lambda document_id: None)
    monkeypatch.setattr(httpx, "post", fail_post)

    notify.notify_status_task.run(
        document_id="00000000-0000-0000-0000-000000000001",
        stage="pipeline",
        status="success",
    )


def test_notify_status_task_posts_to_stored_webhook_url(monkeypatch) -> None:
    posted_urls: list[str] = []

    def record_post(url, *args, **kwargs):
        posted_urls.append(url)
        return httpx.Response(200, request=httpx.Request("POST", url))

    monkeypatch.setattr(
        notify,
        "_load_webhook_url",
        lambda document_id: "http://stored.test/api/v1/kb/webhook",
    )
    monkeypatch.setattr(httpx, "post", record_post)

    notify.notify_status_task.run(
        document_id="00000000-0000-0000-0000-000000000001",
        stage="pipeline",
        status="success",
    )

    assert posted_urls == ["http://stored.test/api/v1/kb/webhook"]


def test_build_status_payload_includes_summary_source_identity_and_safe_counts() -> None:
    payload = notify._build_status_payload(
        document_id="00000000-0000-0000-0000-000000000001",
        status="success",
        stage="pipeline",
        error_message=None,
        document_metadata={
            "source_type": "conversation_file",
            "conversation_id": "00000000-0000-0000-0000-000000000002",
            "conversation_file_id": "00000000-0000-0000-0000-000000000003",
            "source_uri": "https://storage.test/file.pdf?signature=secret",
        },
        summary="One-sentence orientation summary.",
        metadata={
            "chunk_count": 3,
            "raw_text": "private contract text",
            "signed_url": "https://storage.test/secret",
            "model_input": "private summary prompt",
            "model_inputs": ["private model batch"],
        },
        timestamp=123,
    )

    assert payload["summary"] == "One-sentence orientation summary."
    assert payload["source_type"] == "conversation_file"
    assert payload["conversation_id"] == "00000000-0000-0000-0000-000000000002"
    assert payload["conversation_file_id"] == "00000000-0000-0000-0000-000000000003"
    assert payload["metadata"] == {"chunk_count": 3}
    assert "signature=secret" not in repr(payload)
    assert "private contract text" not in repr(payload)
    assert "private summary prompt" not in repr(payload)
    assert "private model batch" not in repr(payload)


def test_dead_letter_log_redacts_secret_values(monkeypatch) -> None:
    secret_error = (
        "LITELLM_API_KEY=sk-test-secret KB_API_SECRET=super-secret "
        "Authorization: Bearer private-token"
    )

    with capture_logs(processors=[redact_event_dict]) as logs:
        notify._handle_webhook_dead_letter(
            task_id="task-1",
            document_id=None,
            stage="pipeline",
            status="success",
            exc=RuntimeError(secret_error),
        )

    rendered_logs = repr(logs)
    assert "sk-test-secret" not in rendered_logs
    assert "super-secret" not in rendered_logs
    assert "private-token" not in rendered_logs
    assert "[REDACTED]" in rendered_logs
