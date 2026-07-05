"""Shared validation helpers for backend-owned uploads."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any, BinaryIO

from app.core.exceptions import (
    FileTooLargeError,
    UnsupportedFileTypeError,
    ValidationError,
)

SUPPORTED_KB_CONTENT_TYPES = {
    "application/pdf",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "application/vnd.openxmlformats-officedocument.presentationml.presentation",
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
}

SUPPORTED_CONVERSATION_FILE_TYPES = {
    ".pdf": "application/pdf",
    ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    ".pptx": "application/vnd.openxmlformats-officedocument.presentationml.presentation",
    ".xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
}

RESERVED_UPLOAD_METADATA_KEYS = {
    "source_type",
    "organization_id",
    "playbook_document_id",
    "conversation_id",
    "conversation_file_id",
    "kb_service_document_id",
    "source_uri",
}


def validate_kb_content_type(filename: str, content_type: str) -> None:
    """Validate an admin KB upload content type."""
    if content_type not in SUPPORTED_KB_CONTENT_TYPES:
        raise UnsupportedFileTypeError(
            filename,
            content_type,
            sorted(SUPPORTED_KB_CONTENT_TYPES),
        )


def validate_kb_metadata_tags(metadata_tags: dict[str, Any]) -> None:
    """Reject client-controlled metadata keys owned by backend/KB-service."""
    reserved = sorted(set(metadata_tags).intersection(RESERVED_UPLOAD_METADATA_KEYS))
    if reserved:
        raise ValidationError(
            f"metadata_tags contains reserved keys: {', '.join(reserved)}"
        )


def validate_conversation_filename(filename: str) -> str:
    """Normalize and validate a browser-provided conversation filename."""
    cleaned = filename.replace("\\", "/").rsplit("/", 1)[-1].strip()
    if not cleaned:
        raise ValidationError("Uploaded file must have a filename")
    if len(cleaned) > 500:
        raise ValidationError("Uploaded filename is too long")
    return cleaned


def validate_conversation_content_type(filename: str, content_type: str) -> str:
    """Validate a conversation-file extension and exact content type pair."""
    lowered = filename.lower()
    extension = next(
        (
            supported_extension
            for supported_extension in SUPPORTED_CONVERSATION_FILE_TYPES
            if lowered.endswith(supported_extension)
        ),
        None,
    )
    allowed_types = sorted(SUPPORTED_CONVERSATION_FILE_TYPES.values())
    if extension is None:
        raise UnsupportedFileTypeError(filename, content_type, allowed_types)

    expected_content_type = SUPPORTED_CONVERSATION_FILE_TYPES[extension]
    if content_type != expected_content_type:
        raise UnsupportedFileTypeError(filename, content_type, allowed_types)
    return expected_content_type


def file_size_bytes(file: BinaryIO, *, restore_position: bool = True) -> int:
    """Return file size while preserving the caller's stream-position contract."""
    position = file.tell()
    file.seek(0, 2)
    size = file.tell()
    file.seek(position if restore_position else 0)
    return size


def validate_conversation_file_size(
    filename: str,
    file: BinaryIO,
    *,
    max_size_bytes: int,
) -> int:
    """Validate a conversation-file stream size."""
    size = file_size_bytes(file)
    validate_declared_upload_size(
        filename,
        size,
        max_size_bytes=max_size_bytes,
    )
    return size


def validate_declared_upload_size(
    filename: str,
    size_bytes: int,
    *,
    max_size_bytes: int,
) -> None:
    """Validate a browser-declared direct-upload size."""
    if size_bytes <= 0:
        raise ValidationError("Uploaded file must not be empty")
    if size_bytes > max_size_bytes:
        raise FileTooLargeError(filename, size_bytes, max_size_bytes)


def validate_pending_upload_request(expires_at: datetime) -> None:
    """Reject pending direct-upload completion after its storage contract expires."""
    if expires_at <= datetime.now(UTC):
        raise ValidationError("Upload request has expired")


def raise_for_upload_verification_failure(status: str) -> None:
    """Map storage verification status to stable public validation errors."""
    if status == "valid":
        return
    if status == "missing":
        raise ValidationError("Uploaded object is missing")
    raise ValidationError("Uploaded object does not match request metadata")
