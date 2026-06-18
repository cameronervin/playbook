"""S3 object inspection helpers for ingestion."""

from __future__ import annotations

import asyncio
import hashlib

import structlog
from fastapi import HTTPException, status

logger = structlog.get_logger(__name__)


class S3ObjectInspector:
    async def compute_s3_object_md5(self, s3_key: str) -> str:
        return await asyncio.to_thread(self.compute_s3_object_md5_sync, s3_key)

    async def enforce_max_size(self, s3_key: str) -> None:
        """HEAD the S3 object before downloading bytes for MD5 hashing."""
        from app.core.config import settings

        size_bytes = await asyncio.to_thread(self.head_s3_object_size_sync, s3_key)
        max_bytes = settings.KB_MAX_DOCUMENT_SIZE_MB * 1024 * 1024
        if size_bytes > max_bytes:
            mb = size_bytes / (1024 * 1024)
            raise HTTPException(
                status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                detail=(
                    f"Document exceeds maximum size of {settings.KB_MAX_DOCUMENT_SIZE_MB} MB "
                    f"(received {mb:.1f} MB). Split the document or contact the KB admin."
                ),
            )

    def head_s3_object_size_sync(self, s3_key: str) -> int:
        from botocore.exceptions import ClientError

        from app.core.config import settings
        from app.infrastructure.io.s3_tempfile import (
            build_s3_client,
            invalidate_s3_client,
        )

        for attempt in range(2):
            try:
                response = build_s3_client().head_object(
                    Bucket=settings.S3_BUCKET_NAME, Key=s3_key
                )
                return int(response.get("ContentLength", 0))
            except ClientError as exc:
                if (
                    exc.response["Error"]["Code"]
                    in ("ExpiredToken", "InvalidClientTokenId")
                    and attempt == 0
                ):
                    invalidate_s3_client()
                    continue
                raise
        raise RuntimeError("HEAD failed after credential refresh")

    def compute_s3_object_md5_sync(self, s3_key: str) -> str:
        from botocore.exceptions import ClientError

        from app.core.config import settings
        from app.infrastructure.io.s3_tempfile import (
            build_s3_client,
            invalidate_s3_client,
        )

        for attempt in range(2):
            try:
                md5_hash = hashlib.md5()  # noqa: S324
                response = build_s3_client().get_object(
                    Bucket=settings.S3_BUCKET_NAME, Key=s3_key
                )
                body = response["Body"]
                try:
                    while True:
                        chunk = body.read(8 * 1024 * 1024)
                        if not chunk:
                            break
                        md5_hash.update(chunk)
                finally:
                    body.close()
                return md5_hash.hexdigest()
            except ClientError as exc:
                if (
                    exc.response["Error"]["Code"]
                    in ("ExpiredToken", "InvalidClientTokenId")
                    and attempt == 0
                ):
                    invalidate_s3_client()
                    continue
                raise
        raise RuntimeError("MD5 computation failed after credential refresh")


def delete_s3_object(s3_key: str) -> None:
    """Synchronous S3 deletion intended to run via asyncio.to_thread."""
    from app.core.config import settings
    from app.infrastructure.io.s3_tempfile import build_s3_client

    client = build_s3_client()
    try:
        client.delete_object(Bucket=settings.S3_BUCKET_NAME, Key=s3_key)
        logger.info("kb_s3_object_deleted", s3_key=s3_key)
    except Exception as exc:
        logger.warning("kb_s3_delete_failed", s3_key=s3_key, error=str(exc))
