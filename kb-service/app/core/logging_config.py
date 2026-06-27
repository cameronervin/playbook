"""Central logging setup with pre-render secret redaction."""
from __future__ import annotations

import logging
from typing import Any

import structlog

from app.core.log_redaction import redact_event_dict, redact_secrets, redact_string

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
    try:
        record.msg = redact_string(record.getMessage())
        record.args = ()
    except (TypeError, ValueError):
        record.msg = redact_secrets(record.msg)
        record.args = redact_secrets(record.args)
    record.exc_text = redact_string(record.exc_text) if record.exc_text else None
    record.stack_info = redact_string(record.stack_info) if record.stack_info else None
    for key, value in list(record.__dict__.items()):
        if key not in _BASE_LOG_RECORD_KEYS:
            setattr(record, key, redact_secrets(value))


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
