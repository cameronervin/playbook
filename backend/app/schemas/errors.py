"""Pydantic schemas for standardized API error responses."""

from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class ErrorResponse(BaseModel):
    """Standardized error response schema.

    All API errors return this format for consistency.
    """

    error_code: str = Field(
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

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "error_code": "AGENT_FAILED",
                "message": "Agent execution failed after 3 retry attempts",
                "retryable": True,
                "details": {"request_id": "123e4567-e89b-12d3-a456-426614174000"},
            }
        }
    )


class ValidationErrorDetail(BaseModel):
    """Detail for a single validation error (FastAPI RequestValidationError)."""

    loc: list[str | int] = Field(..., description="Location of the error (e.g. ['body', 'email'])")
    msg: str = Field(..., description="Error message")
    type: str = Field(..., description="Error type")


class ValidationErrorResponse(ErrorResponse):
    """Validation error response with field-level details (422)."""

    error_code: str = Field(default="VALIDATION_ERROR", description="Always VALIDATION_ERROR")
    validation_errors: list[ValidationErrorDetail] = Field(
        default_factory=list,
        description="List of specific validation errors",
    )
