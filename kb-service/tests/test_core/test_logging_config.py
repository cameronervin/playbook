from __future__ import annotations

import io
import logging

import structlog
from uvicorn.logging import AccessFormatter

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


def test_stdlib_filter_preserves_uvicorn_access_formatter_args() -> None:
    record = logging.LogRecord(
        name="uvicorn.access",
        level=logging.INFO,
        pathname=__file__,
        lineno=1,
        msg='%s - "%s %s HTTP/%s" %d',
        args=(
            "127.0.0.1:5555",
            "GET",
            "/health?Authorization=Bearer token-secret",
            "1.1",
            200,
        ),
        exc_info=None,
    )

    SecretRedactionFilter().filter(record)

    assert len(record.args) == 5
    rendered = AccessFormatter(
        '%(client_addr)s - "%(request_line)s" %(status_code)s'
    ).format(record)
    assert "GET /health?Authorization=" in rendered
    assert "token-secret" not in rendered
    assert "[REDACTED]" in rendered


def test_configure_logging_keeps_noisy_sdk_loggers_above_debug() -> None:
    noisy_loggers = ("botocore", "boto3", "s3transfer", "httpcore", "httpx", "openai")
    original_root_level = logging.getLogger().level
    original_levels = {
        name: logging.getLogger(name).level
        for name in noisy_loggers + ("botocore.auth", "openai._base_client")
    }
    try:
        logging.getLogger("botocore.auth").setLevel(logging.DEBUG)
        logging.getLogger("openai._base_client").setLevel(logging.DEBUG)

        configure_logging("DEBUG")

        for logger_name in noisy_loggers + ("botocore.auth", "openai._base_client"):
            assert logging.getLogger(logger_name).getEffectiveLevel() > logging.DEBUG
    finally:
        logging.getLogger().setLevel(original_root_level)
        for logger_name, level in original_levels.items():
            logging.getLogger(logger_name).setLevel(level)
