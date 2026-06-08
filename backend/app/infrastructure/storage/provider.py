"""Abstract storage provider interface."""

from abc import ABC, abstractmethod
from collections.abc import AsyncGenerator
from typing import BinaryIO


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
    async def file_exists(self, key: str) -> bool:
        """Check whether a file exists at the given key."""
