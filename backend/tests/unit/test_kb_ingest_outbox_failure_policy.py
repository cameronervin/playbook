"""Tests for KB ingest outbox failure policy decisions."""

from __future__ import annotations

from app.core.exceptions import (
    KBConnectionError,
    KBValidationError,
    StorageError,
    ValidationError,
)
from app.services.kb_ingest_outbox.failure_policy import (
    SAFE_FAILURE_REASON,
    OutboxFailurePolicy,
    OutboxResourceMismatchError,
    OutboxResourceMissingError,
)


def test_failure_policy_classifies_retryable_and_terminal_errors(
    test_settings,
) -> None:
    policy = OutboxFailurePolicy(test_settings)

    assert policy.is_retryable(KBConnectionError("temporary outage")) is True
    assert policy.is_retryable(StorageError("storage timeout", retryable=True)) is True
    assert policy.is_retryable(ValidationError("temporary", details={})) is False
    assert policy.is_retryable(KBValidationError("bad request")) is False
    assert policy.is_retryable(RuntimeError("unexpected")) is False


def test_failure_policy_resource_errors_do_not_count_as_dispatch_attempts(
    test_settings,
) -> None:
    policy = OutboxFailurePolicy(test_settings)

    assert (
        policy.counts_as_dispatch_attempt(OutboxResourceMissingError("missing"))
        is False
    )
    assert (
        policy.counts_as_dispatch_attempt(OutboxResourceMismatchError("mismatch"))
        is False
    )
    assert policy.counts_as_dispatch_attempt(KBConnectionError("down")) is True


def test_failure_policy_sanitizes_and_bounds_failure_metadata(test_settings) -> None:
    policy = OutboxFailurePolicy(test_settings)
    exc = KBConnectionError(
        "x" * 600 + " https://storage.example/private.pdf?signature=topsecret"
    )

    metadata = policy.failure_metadata(exc, retryable=True, attempt_count=1)

    assert metadata["error_type"] == "KBConnectionError"
    assert metadata["retryable"] is True
    assert metadata["attempt_count"] == 1
    assert metadata["max_attempts"] == test_settings.KB_RETRY_ATTEMPTS
    assert metadata["message"] == SAFE_FAILURE_REASON
    assert "topsecret" not in repr(metadata)
    assert "https://storage.example" not in repr(metadata)


def test_failure_policy_safe_message_fallback_and_length_bound(test_settings) -> None:
    policy = OutboxFailurePolicy(test_settings)

    assert policy.safe_message(RuntimeError("")) == SAFE_FAILURE_REASON
    assert len(policy.safe_message(RuntimeError("x" * 600))) == 500


def test_failure_policy_retry_delay_uses_linear_cap(test_settings) -> None:
    policy = OutboxFailurePolicy(test_settings)

    assert policy.retry_delay_seconds(1) == test_settings.KB_RETRY_BACKOFF_BASE
    assert policy.retry_delay_seconds(999) == test_settings.KB_RETRY_BACKOFF_CAP
