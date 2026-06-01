"""Storage path utilities for consistent S3 key generation.

Centralizes key construction so files are organized consistently in the bucket:

- Uploaded files:  examples/{example_id}/uploads/{filename}
- Generated files: examples/{example_id}/generated/{category}/{filename}

Replace the ``examples/...`` prefixes with your own entity hierarchy as the
app grows. Keeping key construction here (not inline) keeps the layout easy to
evolve.
"""

from datetime import UTC, datetime
from uuid import UUID

UPLOADS_PREFIX = "uploads"
GENERATED_PREFIX = "generated"

# Default category folder under generated/.
CATEGORY_EXPORTS = "exports"


def uploaded_file_key(example_id: UUID, filename: str) -> str:
    """Generate an S3 key for user-uploaded files.

    Returns:
        examples/{example_id}/uploads/{filename}
    """
    return f"examples/{example_id}/{UPLOADS_PREFIX}/{filename}"


def generated_file_key(
    example_id: UUID,
    filename: str,
    category: str = CATEGORY_EXPORTS,
) -> str:
    """Generate a timestamped S3 key for generated files (keeps version history).

    Returns:
        examples/{example_id}/generated/{category}/{timestamp}_{filename}
    """
    timestamp = datetime.now(UTC).strftime("%Y%m%d_%H%M%S")
    return f"examples/{example_id}/{GENERATED_PREFIX}/{category}/{timestamp}_{filename}"


def generated_file_key_static(example_id: UUID, filename: str, category: str) -> str:
    """Generate a fixed S3 key for files that should be overwritten on re-generation.

    Returns:
        examples/{example_id}/generated/{category}/{filename}
    """
    return f"examples/{example_id}/{GENERATED_PREFIX}/{category}/{filename}"
