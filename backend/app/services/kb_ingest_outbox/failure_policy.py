"""Failure classification for durable KB ingest outbox dispatch."""

from __future__ import annotations

import re
from typing import Any

from app.core.config import Settings
from app.core.exceptions import (
    AppError,
    KBAuthError,
    KBConfigError,
    KBConnectionError,
    KBTimeoutError,
    KBValidationError,
    StorageError,
)
from app.core.log_redaction import redact_string

SAFE_FAILURE_REASON = "KB ingestion dispatch failed"

_URL_RE = re.compile(r"https?://[^\s,)]+")
_RETRYABLE_KB_ERRORS = (KBConnectionError, KBTimeoutError)
_TERMINAL_KB_ERRORS = (KBAuthError, KBValidationError, KBConfigError)


class OutboxResourceMissingError(RuntimeError):
    """Raised when an outbox row no longer has its backend resource."""


class OutboxResourceMismatchError(RuntimeError):
    """Raised when an outbox row disagrees with trusted backend metadata."""


class OutboxFailurePolicy:
    """Classify outbox dispatch failures and build safe metadata."""

    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    @staticmethod
    def is_retryable(exc: Exception) -> bool:
        """Return whether a dispatch failure should be retried."""
        if isinstance(exc, _TERMINAL_KB_ERRORS):
            return False
        if isinstance(exc, _RETRYABLE_KB_ERRORS):
            return True
        if isinstance(exc, StorageError):
            return exc.retryable
        if isinstance(exc, AppError):
            return exc.retryable
        return False

    @staticmethod
    def counts_as_dispatch_attempt(exc: Exception) -> bool:
        """Return whether a failure reached provider/storage dispatch work."""
        return not isinstance(
            exc,
            (OutboxResourceMissingError, OutboxResourceMismatchError),
        )

    def failure_metadata(
        self,
        exc: Exception,
        *,
        retryable: bool,
        attempt_count: int,
    ) -> dict[str, Any]:
        """Return sanitized, bounded failure metadata for persistence."""
        return {
            "error_type": type(exc).__name__,
            "retryable": retryable,
            "attempt_count": attempt_count,
            "max_attempts": self.settings.KB_RETRY_ATTEMPTS,
            "message": self.safe_message(exc),
        }

    @staticmethod
    def safe_message(exc: Exception) -> str:
        """Return a safe bounded exception message for metadata."""
        message = redact_string(str(exc))
        if _URL_RE.search(message):
            return SAFE_FAILURE_REASON
        return message[:500] or SAFE_FAILURE_REASON

    def retry_delay_seconds(self, attempt_count: int) -> int:
        """Return the linear retry delay clamped to the configured cap."""
        delay = self.settings.KB_RETRY_BACKOFF_BASE * attempt_count
        return min(delay, self.settings.KB_RETRY_BACKOFF_CAP)
