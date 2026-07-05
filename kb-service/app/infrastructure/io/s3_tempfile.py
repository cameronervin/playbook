"""Streaming S3 -> path-backed temp file utilities.

Streams an S3 object to a temp file on disk chunk by chunk so peak RAM is
bounded to ``chunk_size`` (8 MB default) regardless of object size. Both an
async context manager (network I/O offloaded to a thread via
``asyncio.to_thread``) and a sync context manager are provided; the temp file
is always deleted on context exit.

The S3 client is sourced from ``io/s3_client.py``. ``_sync_stream_to_path``
retries once on expired/invalid temporary credentials by invalidating the
cached client and rebuilding it. ``boto3``'s exception types are imported
lazily so this module compiles without boto3 installed.
"""
from __future__ import annotations

import asyncio
import os
import tempfile
from contextlib import asynccontextmanager, contextmanager
from pathlib import Path
from typing import AsyncIterator, Iterator
from urllib.parse import unquote, urlparse

import structlog

from app.core.config import settings
from app.infrastructure.io.s3_client import build_s3_client, invalidate_s3_client

logger = structlog.get_logger(__name__)


def extract_s3_parts(presigned_url: str) -> tuple[str, str]:
    parsed = urlparse(presigned_url)
    path = unquote(parsed.path).lstrip("/")
    hostname = parsed.hostname or ""
    # Virtual-hosted style: {bucket}.s3.{region}.amazonaws.com — path IS the key
    if ".s3." in hostname and "amazonaws.com" in hostname:
        bucket = hostname.split(".s3.")[0]
        key = path
    else:
        # Path-style (MinIO or path-style AWS): /{bucket}/{key}
        bucket, _, key = path.partition("/")
    if not bucket or not key:
        raise ValueError(f"Could not parse S3 bucket/key from URL: {presigned_url}")
    return bucket, key


def _sync_stream_to_path(
    *,
    bucket: str,
    s3_key: str,
    dest_path: str,
    chunk_size: int,
    max_file_size: int,
) -> int:
    """Sync worker: stream S3 object to dest_path chunk by chunk. Returns bytes written.

    Runs inside asyncio.to_thread — never call from async context directly.
    Auto-refreshes the S3 client once on expired/invalid temporary credentials.
    """
    from botocore.exceptions import ClientError

    for attempt in range(2):
        body = None
        try:
            response = build_s3_client().get_object(Bucket=bucket, Key=s3_key)
            body = response["Body"]
            bytes_read = 0
            with open(dest_path, "wb") as f:
                while True:
                    chunk = body.read(chunk_size)
                    if not chunk:
                        break
                    bytes_read += len(chunk)
                    if bytes_read > max_file_size:
                        raise ValueError(
                            f"S3 object exceeds size limit: {settings.S3_STREAM_MAX_FILE_SIZE_MB} MB"
                        )
                    f.write(chunk)
        except ClientError as exc:
            if exc.response["Error"]["Code"] in ("ExpiredToken", "InvalidClientTokenId") and attempt == 0:
                invalidate_s3_client()
                continue
            raise
        else:
            return bytes_read
        finally:
            if body is not None:
                body.close()
    raise RuntimeError("S3 stream failed after credential refresh")


@asynccontextmanager
async def stream_s3_object_to_tempfile(
    *,
    bucket: str,
    s3_key: str,
    suffix: str = "",
    chunk_size: int = 8 * 1024 * 1024,
) -> AsyncIterator[str]:
    """Async: stream an S3 object to a temp file on disk without loading it into RAM.

    S3 network I/O runs in a thread pool via asyncio.to_thread so the event loop
    stays free. Peak RAM is bounded to chunk_size (8 MB default) regardless of
    file size. The temp file is deleted on context exit.

    Usage (inside async functions):
        async with stream_s3_object_to_tempfile(bucket=b, s3_key=k) as path:
            ...process file at path...
    """
    max_file_size = settings.S3_STREAM_MAX_FILE_SIZE_MB * 1024 * 1024
    fd, tmp_path = tempfile.mkstemp(suffix=suffix)
    os.close(fd)
    try:
        bytes_read = await asyncio.to_thread(
            _sync_stream_to_path,
            bucket=bucket,
            s3_key=s3_key,
            dest_path=tmp_path,
            chunk_size=chunk_size,
            max_file_size=max_file_size,
        )
        logger.info(
            "s3_stream_to_tempfile_complete",
            bucket=bucket,
            s3_key=s3_key,
            bytes_read=bytes_read,
        )
        yield tmp_path
    finally:
        if tmp_path and Path(tmp_path).exists():
            os.unlink(tmp_path)


@contextmanager
def stream_s3_object_to_tempfile_sync(
    *,
    bucket: str,
    s3_key: str,
    suffix: str = "",
    chunk_size: int = 8 * 1024 * 1024,
) -> Iterator[str]:
    """Sync variant for use in non-async contexts (e.g. parsers called from the worker router).

    Same disk-streaming behaviour as the async version — no full file in RAM.
    """
    max_file_size = settings.S3_STREAM_MAX_FILE_SIZE_MB * 1024 * 1024
    fd, tmp_path = tempfile.mkstemp(suffix=suffix)
    os.close(fd)
    try:
        bytes_read = _sync_stream_to_path(
            bucket=bucket,
            s3_key=s3_key,
            dest_path=tmp_path,
            chunk_size=chunk_size,
            max_file_size=max_file_size,
        )
        logger.info(
            "s3_stream_to_tempfile_complete",
            bucket=bucket,
            s3_key=s3_key,
            bytes_read=bytes_read,
        )
        yield tmp_path
    finally:
        if tmp_path and Path(tmp_path).exists():
            os.unlink(tmp_path)
