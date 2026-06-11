"""Retry handler for agent operations with exponential backoff.

Pattern: a single ``RetryHandler`` wraps async operations and retries only on
errors it deems transient. Retryability is decided by:
    1. ``AppError.retryable`` for the app's own exceptions, else
    2. a set of provider-agnostic transient error types.

This keeps retry policy in one place and lets nodes/executors stay clean.
"""

import asyncio
from collections.abc import Awaitable, Callable
from typing import TypeVar

import structlog

from app.core.config import Settings, get_settings
from app.core.exceptions import AppError

logger = structlog.get_logger(__name__)

T = TypeVar("T")


class RetryHandler:
    """Retries async operations with exponential backoff."""

    # Provider-agnostic transient error types. Add SDK-specific exceptions here
    # (e.g. anthropic.RateLimitError) when a concrete provider SDK is wired in.
    LEGACY_RETRYABLE_ERRORS: tuple[type[Exception], ...] = (
        asyncio.TimeoutError,
        TimeoutError,
        ConnectionError,
    )

    def __init__(
        self,
        max_attempts: int | None = None,
        backoff_seconds: float | None = None,
        settings: Settings | None = None,
    ):
        """Initialize the retry handler (defaults sourced from settings)."""
        app_settings = settings or get_settings()
        self.max_attempts = max_attempts or app_settings.AGENT_MAX_RETRIES
        self.backoff_seconds = backoff_seconds or app_settings.AGENT_RETRY_BACKOFF

    def is_retryable(self, error: Exception) -> bool:
        """Decide whether an error should trigger a retry."""
        if isinstance(error, AppError):
            return error.retryable
        return isinstance(error, self.LEGACY_RETRYABLE_ERRORS)

    async def retry_with_backoff(
        self,
        operation: Callable[[], Awaitable[T]],
        operation_name: str = "Agent operation",
    ) -> T:
        """Retry an async operation with exponential backoff.

        Raises:
            Exception: The last exception if all retries fail.
        """
        last_exception: Exception | None = None

        for attempt in range(1, self.max_attempts + 1):
            try:
                logger.info(f"{operation_name}: Attempt {attempt}/{self.max_attempts}")
                result = await operation()
            except Exception as e:
                last_exception = e

                if not self.is_retryable(e):
                    logger.exception(
                        f"{operation_name}: Non-retryable error on attempt {attempt}: "
                        f"{type(e).__name__}"
                    )
                    raise

                if attempt >= self.max_attempts:
                    logger.exception(
                        f"{operation_name}: Failed after {self.max_attempts} attempts. "
                        f"Last error: {type(e).__name__}"
                    )
                    raise

                backoff = self.backoff_seconds * (2 ** (attempt - 1))
                logger.warning(
                    f"{operation_name}: Retryable error on attempt {attempt}: "
                    f"{type(e).__name__}: {str(e)}. Retrying in {backoff:.1f}s..."
                )
                await asyncio.sleep(backoff)
            else:
                if attempt > 1:
                    logger.info(f"{operation_name}: Succeeded on attempt {attempt}")
                return result

        if last_exception:
            raise last_exception
        raise RuntimeError(f"{operation_name}: Retry loop completed without success or error")
