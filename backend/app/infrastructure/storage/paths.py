"""Storage path utilities for consistent Playbook S3 key generation."""

from datetime import UTC, datetime
from uuid import UUID, uuid4

UPLOADS_PREFIX = "uploads"
GENERATED_PREFIX = "generated"
KB_ORIGINALS_PREFIX = "kb/originals"
CONVERSATION_UPLOADS_PREFIX = "conversations"

# Default category folder under generated/.
CATEGORY_EXPORTS = "exports"


def _safe_filename(filename: str) -> str:
    """Return a storage-key-safe filename segment."""
    cleaned = filename.replace("\\", "/").rsplit("/", 1)[-1].strip()
    return cleaned or "upload.bin"


def kb_original_file_key(organization_id: UUID, filename: str) -> str:
    """Generate an S3 key for an admin-uploaded KB original."""
    return (
        f"{KB_ORIGINALS_PREFIX}/{organization_id}/{uuid4()}/"
        f"{_safe_filename(filename)}"
    )


def conversation_upload_file_key(
    organization_id: UUID,
    conversation_id: UUID,
    filename: str,
) -> str:
    """Generate an S3 key for a conversation-scoped athlete upload."""
    return (
        f"{CONVERSATION_UPLOADS_PREFIX}/{organization_id}/{conversation_id}/"
        f"{uuid4()}/{_safe_filename(filename)}"
    )


def uploaded_file_key(example_id: UUID, filename: str) -> str:
    """Compatibility wrapper for older scaffold call sites."""
    return f"legacy/{example_id}/{UPLOADS_PREFIX}/{_safe_filename(filename)}"


def generated_file_key(
    example_id: UUID,
    filename: str,
    category: str = CATEGORY_EXPORTS,
) -> str:
    """Generate a timestamped S3 key for generated files."""
    timestamp = datetime.now(UTC).strftime("%Y%m%d_%H%M%S")
    return (
        f"legacy/{example_id}/{GENERATED_PREFIX}/{category}/"
        f"{timestamp}_{_safe_filename(filename)}"
    )


def generated_file_key_static(example_id: UUID, filename: str, category: str) -> str:
    """Generate a fixed S3 key for files that should be overwritten."""
    return f"legacy/{example_id}/{GENERATED_PREFIX}/{category}/{_safe_filename(filename)}"
