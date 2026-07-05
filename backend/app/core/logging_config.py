"""Central logging setup with pre-render secret redaction."""
from __future__ import annotations

import logging
from collections.abc import Mapping, Sequence
from typing import Any

import structlog

from app.core.log_redaction import (
    REDACTION,
    redact_event_dict,
    redact_secrets,
    redact_string,
)

try:
    from rich.traceback import install as _install_rich_traceback
except ImportError:
    _install_rich_traceback = None

_BASE_LOG_RECORD_KEYS = frozenset(logging.makeLogRecord({}).__dict__)
_ORIGINAL_LOG_RECORD_FACTORY = logging.getLogRecordFactory()
_FILTER_MARKER = "_playbook_secret_redaction_filter"
_FACTORY_MARKER = "_playbook_secret_redaction_factory"
_RICH_TRACEBACK_INSTALLED = False


class SecretRedactionFilter(logging.Filter):
    """Redact secret values on stdlib log records before handler rendering."""

    def filter(self, record: logging.LogRecord) -> bool:
        _redact_log_record(record)
        return True


def configure_logging(log_level: str = "INFO") -> None:
    """Install structlog/stdlib redaction in an idempotent way."""
    resolved_level = _resolve_level(log_level)
    _install_log_record_factory()
    install_secret_redaction_filter(logging.getLogger())
    logging.getLogger().setLevel(resolved_level)
    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,
            redact_event_dict,
            structlog.processors.add_log_level,
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.processors.StackInfoRenderer(),
            structlog.dev.ConsoleRenderer(colors=False),
        ],
        wrapper_class=structlog.make_filtering_bound_logger(resolved_level),
        cache_logger_on_first_use=True,
    )
    _install_safe_rich_tracebacks()


def install_secret_redaction_filter(logger: logging.Logger | None = None) -> None:
    """Attach the stdlib redaction filter to a logger and its current handlers."""
    target = logger or logging.getLogger()
    if not _has_redaction_filter(target.filters):
        target.addFilter(SecretRedactionFilter())
    for handler in target.handlers:
        if not _has_redaction_filter(handler.filters):
            handler.addFilter(SecretRedactionFilter())


def _install_log_record_factory() -> None:
    current_factory = logging.getLogRecordFactory()
    if getattr(current_factory, _FACTORY_MARKER, False):
        return

    def _redacting_factory(*args: Any, **kwargs: Any) -> logging.LogRecord:
        record = _ORIGINAL_LOG_RECORD_FACTORY(*args, **kwargs)
        _redact_log_record(record)
        return record

    setattr(_redacting_factory, _FACTORY_MARKER, True)
    logging.setLogRecordFactory(_redacting_factory)


def _redact_log_record(record: logging.LogRecord) -> None:
    _redact_exception_args(record)
    record.msg = redact_secrets(record.msg)
    record.args = _redact_log_args(record.msg, record.args)
    record.exc_text = redact_string(record.exc_text) if record.exc_text else None
    record.stack_info = redact_string(record.stack_info) if record.stack_info else None
    for key, value in list(record.__dict__.items()):
        if key not in _BASE_LOG_RECORD_KEYS:
            setattr(record, key, redact_secrets(value))


def _redact_log_args(message: Any, args: Any) -> Any:
    redacted_args = redact_secrets(args)
    if not _message_template_has_sensitive_placeholder(message):
        return redacted_args
    return _redact_string_args(redacted_args)


def _message_template_has_sensitive_placeholder(message: Any) -> bool:
    if not isinstance(message, str) or "%" not in message:
        return False
    normalized = message.lower().replace("-", "_")
    sensitive_markers = (
        "api_key",
        "apikey",
        "secret",
        "token",
        "password",
        "passwd",
        "authorization",
        "bearer",
        "signature",
        "database_url",
        "db_url",
        "access_key",
        "private_key",
        "source_uri",
        "presigned_url",
        "signed_url",
    )
    return any(marker in normalized for marker in sensitive_markers)


def _redact_string_args(value: Any) -> Any:
    if isinstance(value, str):
        return REDACTION
    if isinstance(value, Mapping):
        return {
            key: REDACTION if isinstance(item, str) else _redact_string_args(item)
            for key, item in value.items()
        }
    if isinstance(value, tuple):
        return tuple(_redact_string_args(item) for item in value)
    if isinstance(value, Sequence) and not isinstance(value, (bytes, bytearray)):
        return [_redact_string_args(item) for item in value]
    return value


def _redact_exception_args(record: logging.LogRecord) -> None:
    if not record.exc_info:
        return
    exc = record.exc_info[1]
    if exc is None or not hasattr(exc, "args"):
        return
    try:
        exc.args = tuple(redact_secrets(arg) for arg in exc.args)
    except (AttributeError, TypeError):
        return


def _has_redaction_filter(filters: list[logging.Filter]) -> bool:
    return any(getattr(item, _FILTER_MARKER, False) for item in filters)


def _resolve_level(log_level: str) -> int:
    return int(getattr(logging, str(log_level).upper(), logging.INFO))


def _install_safe_rich_tracebacks() -> None:
    global _RICH_TRACEBACK_INSTALLED
    if _RICH_TRACEBACK_INSTALLED:
        return
    if _install_rich_traceback is None:
        _RICH_TRACEBACK_INSTALLED = True
        return
    _install_rich_traceback(show_locals=False)
    _RICH_TRACEBACK_INSTALLED = True


setattr(SecretRedactionFilter, _FILTER_MARKER, True)
