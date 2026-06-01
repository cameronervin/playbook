"""Global exception handlers for FastAPI."""

from enum import Enum

import structlog
from fastapi import Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.core.exceptions import AppError
from app.schemas.errors import (
    ErrorResponse,
    ValidationErrorDetail,
    ValidationErrorResponse,
)

logger = structlog.get_logger(__name__)


def _http_exception_message(detail: object) -> str:
    """Stringify HTTPException.detail for the API `message` field.

    `str(some_str_enum)` is often `ClassName.MEMBER`; clients need the value.
    """
    if isinstance(detail, Enum):
        v = detail.value
        if isinstance(v, str):
            return v
        if v is not None:
            return str(v)
    return str(detail)


async def app_error_handler(request: Request, exc: AppError) -> JSONResponse:
    """Handle custom AppError exceptions with standardized response."""
    logger.error(
        "Application error",
        path=request.url.path,
        method=request.method,
        error_code=exc.error_code.value,
        error_message=exc.message,
        retryable=exc.retryable,
        status_code=exc.status,
        exc_info=True,
    )

    error_response = ErrorResponse(
        error_code=exc.error_code.value,
        message=exc.message,
        retryable=exc.retryable,
        details=exc.details,
    )

    return JSONResponse(status_code=exc.status, content=error_response.model_dump())


async def http_exception_handler(request: Request, exc: StarletteHTTPException) -> JSONResponse:
    """Handle HTTPException with standardized response format."""
    logger.warning(
        "HTTP exception",
        path=request.url.path,
        method=request.method,
        status_code=exc.status_code,
        detail=exc.detail,
    )

    error_code_map = {
        400: "VALIDATION_ERROR",
        401: "UNAUTHORIZED",
        403: "FORBIDDEN",
        404: "NOT_FOUND",
        429: "RATE_LIMIT_EXCEEDED",
        500: "INTERNAL_SERVER_ERROR",
        503: "SERVICE_UNAVAILABLE",
        504: "TIMEOUT",
    }
    error_code = error_code_map.get(exc.status_code, "UNKNOWN_ERROR")
    retryable = exc.status_code in (429, 500, 503, 504)

    error_response = ErrorResponse(
        error_code=error_code,
        message=_http_exception_message(exc.detail),
        retryable=retryable,
        details={},
    )

    return JSONResponse(status_code=exc.status_code, content=error_response.model_dump())


async def validation_exception_handler(request: Request, exc: RequestValidationError) -> JSONResponse:
    """Handle Pydantic validation errors with standardized response."""
    logger.warning(
        "Request validation failed",
        path=request.url.path,
        method=request.method,
        errors=exc.errors(),
    )

    validation_errors = [
        ValidationErrorDetail(
            loc=[str(loc) for loc in error["loc"]],
            msg=error["msg"],
            type=error["type"],
        )
        for error in exc.errors()
    ]

    error_response = ValidationErrorResponse(
        error_code="VALIDATION_ERROR",
        message="Request validation failed",
        retryable=False,
        details={},
        validation_errors=validation_errors,
    )

    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content=error_response.model_dump(),
    )


async def generic_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """Handle unexpected exceptions with standardized response."""
    logger.error(
        "Unexpected error",
        path=request.url.path,
        method=request.method,
        error=str(exc),
        error_type=type(exc).__name__,
        exc_info=True,
    )

    error_response = ErrorResponse(
        error_code="INTERNAL_SERVER_ERROR",
        message="An unexpected error occurred",
        retryable=False,
        details={"error_type": type(exc).__name__},
    )

    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content=error_response.model_dump(),
    )
