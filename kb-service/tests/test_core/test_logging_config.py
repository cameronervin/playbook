from __future__ import annotations

import io
import logging

import structlog

from app.core.logging_config import SecretRedactionFilter, configure_logging


def test_configure_logging_installs_structlog_redaction_once() -> None:
    configure_logging("INFO")
    configure_logging("INFO")

    processors = structlog.get_config()["processors"]

    assert sum(getattr(processor, "__name__", "") == "redact_event_dict" for processor in processors) == 1


def test_structlog_processor_redacts_before_rendering() -> None:
    configure_logging("INFO")
    event = {
        "event": "test_event",
        "LITELLM_API_KEY": "sk-litellm-secret",
        "headers": {"Authorization": "Bearer token-secret"},
        "database_url": "postgresql://user:pass@localhost/db",
        "message": "X-KB-Signature=sha256=signature-secret",
    }

    rendered = repr(structlog.get_config()["processors"][1](None, "info", event))

    assert "sk-litellm-secret" not in rendered
    assert "token-secret" not in rendered
    assert "user:pass" not in rendered
    assert "signature-secret" not in rendered
    assert "[REDACTED]" in rendered


def test_stdlib_filter_redacts_message_args_extra_and_exception_text() -> None:
    stream = io.StringIO()
    handler = logging.StreamHandler(stream)
    handler.addFilter(SecretRedactionFilter())
    handler.setFormatter(logging.Formatter("%(message)s %(api_key)s"))

    logger = logging.getLogger("test.secret_redaction.kb_service")
    logger.handlers = [handler]
    logger.propagate = False
    logger.setLevel(logging.INFO)

    secret_error = "DATABASE_URL=postgresql://user:" + "pass@localhost/db"
    try:
        raise RuntimeError(secret_error)
    except RuntimeError:
        logger.exception(
            "failed Authorization: Bearer %s",
            "token-secret",
            extra={"api_key": "sk-extra-secret"},
        )

    rendered = stream.getvalue()
    assert "user:pass" not in rendered
    assert "token-secret" not in rendered
    assert "sk-extra-secret" not in rendered
    assert "[REDACTED]" in rendered
