"""Pydantic schemas for standardized API error responses."""

from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class ErrorDetail(BaseModel):
    """Nested API error detail."""

    code: str = Field(
        ...,
        description="Standardized error code identifying the error type",
        examples=["VALIDATION_ERROR", "AGENT_FAILED", "NOT_FOUND"],
    )
    message: str = Field(
        ...,
        description="Human-readable error message",
        examples=["File not found", "Request validation failed"],
    )
    retryable: bool = Field(
        ...,
        description="Whether the error is transient and the operation can be retried",
        examples=[True, False],
    )
    details: dict[str, Any] = Field(
        default_factory=dict,
        description="Additional context about the error (request_id, resource IDs, etc.)",
    )


class ErrorResponse(BaseModel):
    """Standardized nested API error response."""

    error: ErrorDetail

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "error": {
                    "code": "AGENT_FAILED",
                    "message": "Agent execution failed after 3 retry attempts",
                    "retryable": True,
                    "details": {"request_id": "123e4567-e89b-12d3-a456-426614174000"},
                }
            }
        }
    )


class ValidationErrorDetail(BaseModel):
    """Detail for a single validation error (FastAPI RequestValidationError)."""

    loc: list[str | int] = Field(..., description="Location of the error (e.g. ['body', 'email'])")
    msg: str = Field(..., description="Error message")
    type: str = Field(..., description="Error type")


__all__ = [
    "ErrorDetail",
    "ErrorResponse",
    "ValidationErrorDetail",
]
