"""Tests for storage provider direct-upload support."""

from __future__ import annotations

from collections.abc import AsyncGenerator
from datetime import UTC, datetime, timedelta
from typing import BinaryIO

import pytest

from app.infrastructure.storage.provider import (
    ObjectVerificationResult,
    PresignedPostUpload,
    StorageProvider,
    StoredObjectMetadata,
)


class MetadataStorageProvider(StorageProvider):
    """Minimal concrete provider for exercising default verification logic."""

    def __init__(self, metadata: StoredObjectMetadata | None) -> None:
        self.metadata = metadata

    async def upload_file(self, key: str, file: BinaryIO, content_type: str) -> str:
        return key

    async def download_file(self, key: str) -> bytes:
        return b""

    async def download_file_stream(
        self, key: str, chunk_size: int = 8 * 1024 * 1024
    ) -> AsyncGenerator[bytes, None]:
        if False:
            yield b""

    async def delete_file(self, key: str) -> None:
        return None

    async def get_presigned_url(
        self,
        key: str,
        expires_in: int = 3600,
        download_filename: str | None = None,
    ) -> str:
        return f"https://storage.example/{key}"

    async def create_presigned_post(
        self,
        *,
        key: str,
        content_type: str,
        max_size_bytes: int,
        expires_in: int | None = None,
    ) -> PresignedPostUpload:
        return PresignedPostUpload(
            url="https://storage.example/upload",
            fields={"key": key, "Content-Type": content_type},
            expires_at=datetime.now(UTC) + timedelta(seconds=expires_in or 3600),
        )

    async def get_object_metadata(self, key: str) -> StoredObjectMetadata | None:
        return self.metadata

    async def file_exists(self, key: str) -> bool:
        return self.metadata is not None


@pytest.mark.asyncio
async def test_verify_object_reports_missing_object() -> None:
    provider = MetadataStorageProvider(metadata=None)

    result = await provider.verify_object(
        key="conversation-files/originals/file.pdf",
        expected_size_bytes=12,
        expected_content_type="application/pdf",
    )

    assert result == ObjectVerificationResult(status="missing")


@pytest.mark.asyncio
async def test_verify_object_reports_size_mismatch() -> None:
    metadata = StoredObjectMetadata(
        key="conversation-files/originals/file.pdf",
        content_length=13,
        content_type="application/pdf",
    )
    provider = MetadataStorageProvider(metadata=metadata)

    result = await provider.verify_object(
        key=metadata.key,
        expected_size_bytes=12,
        expected_content_type="application/pdf",
    )

    assert result == ObjectVerificationResult(
        status="size_mismatch",
        metadata=metadata,
    )


@pytest.mark.asyncio
async def test_verify_object_reports_content_type_mismatch() -> None:
    metadata = StoredObjectMetadata(
        key="conversation-files/originals/file.pdf",
        content_length=12,
        content_type="application/octet-stream",
    )
    provider = MetadataStorageProvider(metadata=metadata)

    result = await provider.verify_object(
        key=metadata.key,
        expected_size_bytes=12,
        expected_content_type="application/pdf",
    )

    assert result == ObjectVerificationResult(
        status="content_type_mismatch",
        metadata=metadata,
    )


@pytest.mark.asyncio
async def test_verify_object_reports_valid_object() -> None:
    metadata = StoredObjectMetadata(
        key="conversation-files/originals/file.pdf",
        content_length=12,
        content_type="application/pdf",
        etag='"abc123"',
        checksum_sha256="sha256",
        user_metadata={"uploaded-by": "playbook"},
    )
    provider = MetadataStorageProvider(metadata=metadata)

    result = await provider.verify_object(
        key=metadata.key,
        expected_size_bytes=12,
        expected_content_type="application/pdf",
    )

    assert result == ObjectVerificationResult(status="valid", metadata=metadata)
