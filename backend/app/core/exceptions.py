"""Custom exceptions."""

from typing import Any

from app.core.error_codes import ErrorCode, get_error_status, is_error_retryable


class AppError(Exception):
    """Base exception for application errors.

    All custom exceptions should inherit from this class to ensure consistent
    error handling across the application.

    Attributes:
        message: Human-readable error message.
        error_code: Standardized error code from ErrorCode enum.
        status: HTTP status code.
        retryable: Whether the error is transient and can be retried.
        details: Optional additional context.
    """

    def __init__(
        self,
        message: str,
        error_code: ErrorCode,
        retryable: bool | None = None,
        details: dict[str, Any] | None = None,
    ):
        self.message = message
        self.error_code = error_code
        self.status = get_error_status(error_code)
        self.retryable = retryable if retryable is not None else is_error_retryable(error_code)
        self.details = details or {}
        self.code = error_code.value  # legacy alias
        super().__init__(message)


class NotFoundError(AppError):
    """Resource not found exception."""

    def __init__(self, resource: str, id: str, details: dict[str, Any] | None = None):
        super().__init__(
            message=f"{resource} not found: {id}",
            error_code=ErrorCode.NOT_FOUND,
            details=details,
        )


class ForbiddenError(AppError):
    """Access denied exception."""

    def __init__(self, message: str = "Access denied", details: dict[str, Any] | None = None):
        super().__init__(message=message, error_code=ErrorCode.FORBIDDEN, details=details)


class UnauthorizedError(AppError):
    """Authentication required or invalid credentials."""

    def __init__(
        self,
        message: str = "Not authenticated",
        details: dict[str, Any] | None = None,
    ):
        super().__init__(message=message, error_code=ErrorCode.UNAUTHORIZED, details=details)


class ConflictError(AppError):
    """Resource conflict exception."""

    def __init__(self, message: str, details: dict[str, Any] | None = None):
        super().__init__(message=message, error_code=ErrorCode.CONFLICT, details=details)


class ValidationError(AppError):
    """Validation error exception."""

    def __init__(self, message: str, details: dict[str, Any] | None = None):
        super().__init__(message=message, error_code=ErrorCode.VALIDATION_ERROR, details=details)


class OAuthError(AppError):
    """OAuth provider or callback failure."""

    def __init__(self, message: str, details: dict[str, Any] | None = None):
        super().__init__(
            message=message,
            error_code=ErrorCode.OAUTH_ERROR,
            retryable=True,
            details=details,
        )


# --- LLM-specific exceptions ---


class LLMError(AppError):
    """Base LLM error."""

    def __init__(
        self,
        message: str,
        error_code: ErrorCode = ErrorCode.AGENT_FAILED,
        provider: str | None = None,
        retryable: bool = True,
        details: dict[str, Any] | None = None,
    ):
        details = details or {}
        if provider:
            details["provider"] = provider
        super().__init__(message=message, error_code=error_code, retryable=retryable, details=details)
        self.provider = provider


class LLMRateLimitError(LLMError):
    """Rate limit exceeded."""

    def __init__(self, message: str, provider: str | None = None, details: dict[str, Any] | None = None):
        super().__init__(
            message=message,
            error_code=ErrorCode.RATE_LIMIT_EXCEEDED,
            provider=provider,
            retryable=True,
            details=details,
        )


class LLMProviderUnavailableError(LLMError):
    """All providers failed."""

    def __init__(self, models: list[str], details: dict[str, Any] | None = None):
        msg = f"All LLM models unavailable: {', '.join(models)}"
        super().__init__(
            message=msg,
            error_code=ErrorCode.PROVIDER_UNAVAILABLE,
            retryable=True,
            details=details,
        )


class LLMTimeoutError(LLMError):
    """LLM request timeout."""

    def __init__(self, message: str, provider: str | None = None, details: dict[str, Any] | None = None):
        super().__init__(
            message=message,
            error_code=ErrorCode.LLM_TIMEOUT,
            provider=provider,
            retryable=True,
            details=details,
        )


# --- Storage-specific exceptions ---


class StorageError(AppError):
    """Base storage error."""

    def __init__(self, message: str, retryable: bool = True, details: dict[str, Any] | None = None):
        super().__init__(
            message=message,
            error_code=ErrorCode.STORAGE_ERROR,
            retryable=retryable,
            details=details,
        )


# --- Database-specific exceptions ---


class DatabaseError(AppError):
    """Database operation failed."""

    def __init__(self, message: str, retryable: bool = True, details: dict[str, Any] | None = None):
        super().__init__(
            message=message,
            error_code=ErrorCode.DATABASE_ERROR,
            retryable=retryable,
            details=details,
        )


# --- Knowledgebase exceptions ---
#
# Exception-to-behavior mapping:
#   KBConnectionError → retryable (linear backoff) → tool returns unavailable message
#   KBTimeoutError    → retryable (linear backoff) → tool returns unavailable message
#   KBAuthError       → NOT retryable → tool returns unavailable message (log CRITICAL)
#   KBValidationError → NOT retryable → tool returns unavailable message (log ERROR)
#   KBConfigError     → NOT retryable → fail-fast on startup (log CRITICAL)


class KnowledgebaseError(AppError):
    """Base exception for all knowledgebase operations."""

    def __init__(
        self,
        message: str,
        error_code: ErrorCode = ErrorCode.KB_CONNECTION_ERROR,
        details: dict[str, Any] | None = None,
    ):
        super().__init__(message=message, error_code=error_code, details=details)


class KBConnectionError(KnowledgebaseError):
    """KB service unreachable (network error, DNS failure)."""

    def __init__(self, message: str, details: dict[str, Any] | None = None):
        super().__init__(message, error_code=ErrorCode.KB_CONNECTION_ERROR, details=details)


class KBTimeoutError(KnowledgebaseError):
    """Request exceeded KB_TIMEOUT seconds."""

    def __init__(self, message: str, details: dict[str, Any] | None = None):
        super().__init__(message, error_code=ErrorCode.KB_TIMEOUT, details=details)


class KBAuthError(KnowledgebaseError):
    """401/403 from KB service — invalid or expired token."""

    def __init__(self, message: str, details: dict[str, Any] | None = None):
        super().__init__(message, error_code=ErrorCode.KB_AUTH_ERROR, details=details)


class KBValidationError(KnowledgebaseError):
    """422 from KB service — request validation failed."""

    def __init__(self, message: str, details: dict[str, Any] | None = None):
        super().__init__(message, error_code=ErrorCode.KB_VALIDATION_ERROR, details=details)


class KBConfigError(KnowledgebaseError):
    """Configuration resolution failed at startup (config not found, API error)."""

    def __init__(self, message: str, details: dict[str, Any] | None = None):
        super().__init__(message, error_code=ErrorCode.KB_CONFIG_ERROR, details=details)


# --- File upload exceptions ---


class FileTooLargeError(ValidationError):
    """File exceeds size limit."""

    def __init__(self, filename: str, size: int, max_size: int, details: dict[str, Any] | None = None):
        details = details or {}
        details.update({"filename": filename, "size_bytes": size, "max_size_bytes": max_size})
        super().__init__(
            message=f"File '{filename}' is too large ({size} bytes). Maximum size is {max_size} bytes.",
            details=details,
        )
        self.error_code = ErrorCode.FILE_TOO_LARGE
        self.status = get_error_status(ErrorCode.FILE_TOO_LARGE)


class UnsupportedFileTypeError(ValidationError):
    """File type not supported."""

    def __init__(self, filename: str, content_type: str, allowed_types: list[str], details: dict[str, Any] | None = None):
        details = details or {}
        details.update({"filename": filename, "content_type": content_type, "allowed_types": allowed_types})
        super().__init__(
            message=f"File type '{content_type}' not supported. Allowed types: {', '.join(allowed_types)}",
            details=details,
        )
        self.error_code = ErrorCode.UNSUPPORTED_FILE_TYPE
        self.status = get_error_status(ErrorCode.UNSUPPORTED_FILE_TYPE)
