"""Abstract storage provider interface."""

from abc import ABC, abstractmethod
from collections.abc import AsyncGenerator
from dataclasses import dataclass, field
from datetime import datetime
from typing import BinaryIO, Literal

ObjectVerificationStatus = Literal[
    "valid",
    "missing",
    "size_mismatch",
    "content_type_mismatch",
]


@dataclass(frozen=True)
class PresignedPostUpload:
    """Browser form POST contract for direct-to-storage uploads."""

    url: str
    fields: dict[str, str]
    expires_at: datetime


@dataclass(frozen=True)
class StoredObjectMetadata:
    """Safe object metadata returned by storage HEAD operations."""

    key: str
    content_length: int
    content_type: str | None = None
    etag: str | None = None
    checksum_crc32: str | None = None
    checksum_crc32c: str | None = None
    checksum_sha1: str | None = None
    checksum_sha256: str | None = None
    user_metadata: dict[str, str] = field(default_factory=dict)


@dataclass(frozen=True)
class ObjectVerificationResult:
    """Result of comparing trusted expected upload metadata to storage HEAD."""

    status: ObjectVerificationStatus
    metadata: StoredObjectMetadata | None = None


class StorageProvider(ABC):
    """Abstract base for file storage backends (S3-compatible, filesystem)."""

    @abstractmethod
    async def upload_file(self, key: str, file: BinaryIO, content_type: str) -> str:
        """Upload a file and return the storage key."""

    @abstractmethod
    async def download_file(self, key: str) -> bytes:
        """Download file content by key."""

    async def download_file_stream(
        self, key: str, chunk_size: int = 8 * 1024 * 1024
    ) -> AsyncGenerator[bytes, None]:
        """Stream file content in chunks. Default falls back to download_file."""
        data = await self.download_file(key)
        for i in range(0, len(data), chunk_size):
            yield data[i : i + chunk_size]

    @abstractmethod
    async def delete_file(self, key: str) -> None:
        """Delete a file by key."""

    @abstractmethod
    async def get_presigned_url(
        self, key: str, expires_in: int = 3600, download_filename: str | None = None
    ) -> str:
        """Generate a presigned/temporary URL for file access.

        Args:
            key: The storage key of the file.
            expires_in: URL expiry time in seconds.
            download_filename: If set, forces a browser download with this
                filename via the Content-Disposition header.
        """

    @abstractmethod
    async def create_presigned_post(
        self,
        *,
        key: str,
        content_type: str,
        max_size_bytes: int,
        expires_in: int | None = None,
    ) -> PresignedPostUpload:
        """Create a browser POST upload contract for one fixed object key."""

    @abstractmethod
    async def get_object_metadata(self, key: str) -> StoredObjectMetadata | None:
        """Return safe object metadata from storage HEAD, or None if missing."""

    async def verify_object(
        self,
        *,
        key: str,
        expected_size_bytes: int,
        expected_content_type: str,
    ) -> ObjectVerificationResult:
        """Verify an uploaded object against trusted backend metadata."""
        metadata = await self.get_object_metadata(key)
        if metadata is None:
            return ObjectVerificationResult(status="missing")
        if metadata.content_length != expected_size_bytes:
            return ObjectVerificationResult(
                status="size_mismatch",
                metadata=metadata,
            )
        if metadata.content_type != expected_content_type:
            return ObjectVerificationResult(
                status="content_type_mismatch",
                metadata=metadata,
            )
        return ObjectVerificationResult(status="valid", metadata=metadata)

    @abstractmethod
    async def file_exists(self, key: str) -> bool:
        """Check whether a file exists at the given key."""
