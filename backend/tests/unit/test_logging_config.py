from __future__ import annotations

import io
import logging

import structlog
from uvicorn.logging import AccessFormatter

from app.core.log_redaction import redact_string
from app.core.logging_config import SecretRedactionFilter, configure_logging


class RaisingStreamHandler(logging.StreamHandler):
    """Make formatter failures fail tests instead of only printing to stderr."""

    def handleError(self, record: logging.LogRecord) -> None:
        raise AssertionError("logging formatter failed") from None


def test_configure_logging_installs_structlog_redaction_once() -> None:
    configure_logging("INFO")
    configure_logging("INFO")

    processors = structlog.get_config()["processors"]

    assert sum(getattr(processor, "__name__", "") == "redact_event_dict" for processor in processors) == 1


def test_structlog_processor_redacts_before_rendering() -> None:
    configure_logging("INFO")
    event = {
        "event": "test_event",
        "OPENAI_API_KEY": "sk-openai-secret",
        "headers": {"Authorization": "Bearer token-secret"},
        "database_url": "postgresql://user:pass@localhost/db",
        "message": "X-KB-Signature=sha256=signature-secret",
    }

    rendered = repr(structlog.get_config()["processors"][1](None, "info", event))

    assert "sk-openai-secret" not in rendered
    assert "token-secret" not in rendered
    assert "user:pass" not in rendered
    assert "signature-secret" not in rendered
    assert "[REDACTED]" in rendered


def test_stdlib_filter_redacts_message_args_extra_and_exception_text() -> None:
    stream = io.StringIO()
    handler = logging.StreamHandler(stream)
    handler.addFilter(SecretRedactionFilter())
    handler.setFormatter(logging.Formatter("%(message)s %(api_key)s"))

    logger = logging.getLogger("test.secret_redaction.backend")
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


def test_uvicorn_access_formatter_survives_stdlib_redaction_factory() -> None:
    stream = io.StringIO()
    handler = RaisingStreamHandler(stream)
    handler.setFormatter(
        AccessFormatter(
            '%(client_addr)s - "%(request_line)s" %(status_code)s',
            use_colors=False,
        )
    )

    logger = logging.getLogger("test.uvicorn.access.backend")
    logger.handlers = [handler]
    logger.propagate = False
    logger.setLevel(logging.INFO)

    configure_logging("INFO")
    logger.info(
        '%s - "%s %s HTTP/%s" %d',
        "127.0.0.1:12345",
        "GET",
        "/api/v1/health",
        "1.1",
        200,
    )

    assert '127.0.0.1:12345 - "GET /api/v1/health HTTP/1.1" 200 OK' in stream.getvalue()


def test_access_log_query_params_are_redacted_without_breaking_formatter() -> None:
    stream = io.StringIO()
    handler = RaisingStreamHandler(stream)
    handler.setFormatter(
        AccessFormatter(
            '%(client_addr)s - "%(request_line)s" %(status_code)s',
            use_colors=False,
        )
    )

    logger = logging.getLogger("test.uvicorn.access.query.backend")
    logger.handlers = [handler]
    logger.propagate = False
    logger.setLevel(logging.INFO)

    configure_logging("INFO")
    logger.info(
        '%s - "%s %s HTTP/%s" %d',
        "127.0.0.1:12345",
        "GET",
        "/api/v1/auth/dev/callback?code=dev-athlete&state=jwt-secret",
        "1.1",
        303,
    )

    rendered = stream.getvalue()
    assert "dev-athlete" not in rendered
    assert "jwt-secret" not in rendered
    assert "code=[REDACTED]" in rendered
    assert "state=[REDACTED]" in rendered


def test_sensitive_query_values_are_redacted_from_strings() -> None:
    value = (
        "https://storage.test/object.pdf?"
        "X-Amz-Credential=minio-access-key&X-Amz-Signature=sig-secret&"
        "X-Amz-Security-Token=session-secret&safe=value"
    )

    redacted = redact_string(value)

    assert "minio-access-key" not in redacted
    assert "sig-secret" not in redacted
    assert "session-secret" not in redacted
    assert "safe=value" in redacted
    assert "X-Amz-Credential=[REDACTED]" in redacted
    assert "X-Amz-Signature=[REDACTED]" in redacted
    assert "X-Amz-Security-Token=[REDACTED]" in redacted
