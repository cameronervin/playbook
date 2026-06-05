"""Error code catalog for standardized API error responses."""

from enum import StrEnum


class ErrorCode(StrEnum):
    """Standardized error codes with HTTP status mappings.

    Each error code maps to a specific HTTP status and indicates whether
    the error is retryable (transient) or permanent.
    """

    # Client errors (4xx) — not retryable
    VALIDATION_ERROR = "VALIDATION_ERROR"
    UNAUTHORIZED = "UNAUTHORIZED"
    NOT_FOUND = "NOT_FOUND"
    FORBIDDEN = "FORBIDDEN"
    CONFLICT = "CONFLICT"
    FILE_TOO_LARGE = "FILE_TOO_LARGE"
    UNSUPPORTED_FILE_TYPE = "UNSUPPORTED_FILE_TYPE"
    OAUTH_ERROR = "OAUTH_ERROR"

    # Rate limiting (429) — retryable
    RATE_LIMIT_EXCEEDED = "RATE_LIMIT_EXCEEDED"

    # Server errors (5xx) — retryable by default
    AGENT_FAILED = "AGENT_FAILED"
    STORAGE_ERROR = "STORAGE_ERROR"
    DATABASE_ERROR = "DATABASE_ERROR"

    # Timeout errors (504) — retryable
    LLM_TIMEOUT = "LLM_TIMEOUT"

    # Service unavailable (503) — retryable
    PROVIDER_UNAVAILABLE = "PROVIDER_UNAVAILABLE"

    # Knowledgebase errors
    KB_CONNECTION_ERROR = "KB_CONNECTION_ERROR"  # 503, retryable — network/DNS failure
    KB_TIMEOUT = "KB_TIMEOUT"                    # 504, retryable — request timed out
    KB_AUTH_ERROR = "KB_AUTH_ERROR"              # 401, not retryable — invalid/expired token
    KB_VALIDATION_ERROR = "KB_VALIDATION_ERROR"  # 422, not retryable — bad request payload
    KB_CONFIG_ERROR = "KB_CONFIG_ERROR"          # 500, not retryable — startup config resolution failure


# Mapping of error codes to HTTP status codes
ERROR_CODE_STATUS_MAP = {
    ErrorCode.VALIDATION_ERROR: 400,
    ErrorCode.UNAUTHORIZED: 401,
    ErrorCode.FORBIDDEN: 403,
    ErrorCode.NOT_FOUND: 404,
    ErrorCode.CONFLICT: 409,
    ErrorCode.FILE_TOO_LARGE: 413,
    ErrorCode.UNSUPPORTED_FILE_TYPE: 415,
    ErrorCode.OAUTH_ERROR: 502,
    ErrorCode.RATE_LIMIT_EXCEEDED: 429,
    ErrorCode.AGENT_FAILED: 500,
    ErrorCode.STORAGE_ERROR: 500,
    ErrorCode.DATABASE_ERROR: 500,
    ErrorCode.PROVIDER_UNAVAILABLE: 503,
    ErrorCode.KB_CONNECTION_ERROR: 503,
    ErrorCode.LLM_TIMEOUT: 504,
    ErrorCode.KB_TIMEOUT: 504,
    ErrorCode.KB_AUTH_ERROR: 401,
    ErrorCode.KB_VALIDATION_ERROR: 422,
    ErrorCode.KB_CONFIG_ERROR: 500,
}


# Mapping of error codes to retryable status
ERROR_CODE_RETRYABLE_MAP = {
    # Non-retryable (permanent errors)
    ErrorCode.VALIDATION_ERROR: False,
    ErrorCode.UNAUTHORIZED: False,
    ErrorCode.NOT_FOUND: False,
    ErrorCode.FORBIDDEN: False,
    ErrorCode.CONFLICT: False,
    ErrorCode.FILE_TOO_LARGE: False,
    ErrorCode.UNSUPPORTED_FILE_TYPE: False,
    ErrorCode.OAUTH_ERROR: True,
    ErrorCode.KB_AUTH_ERROR: False,
    ErrorCode.KB_VALIDATION_ERROR: False,
    ErrorCode.KB_CONFIG_ERROR: False,
    # Retryable (transient errors)
    ErrorCode.RATE_LIMIT_EXCEEDED: True,
    ErrorCode.AGENT_FAILED: True,
    ErrorCode.STORAGE_ERROR: True,
    ErrorCode.DATABASE_ERROR: True,
    ErrorCode.LLM_TIMEOUT: True,
    ErrorCode.PROVIDER_UNAVAILABLE: True,
    ErrorCode.KB_CONNECTION_ERROR: True,
    ErrorCode.KB_TIMEOUT: True,
}


def get_error_status(error_code: ErrorCode) -> int:
    """Get HTTP status code for an error code (defaults to 500)."""
    return ERROR_CODE_STATUS_MAP.get(error_code, 500)


def is_error_retryable(error_code: ErrorCode) -> bool:
    """Check if an error code represents a retryable error (defaults to False)."""
    return ERROR_CODE_RETRYABLE_MAP.get(error_code, False)
