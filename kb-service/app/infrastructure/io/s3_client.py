"""Process-wide cached S3 client builder.

One boto3 S3 client per process, built with thread-safe double-checked locking.
The client honours ``settings.AWS_S3_ENDPOINT_URL`` (set it to a MinIO URL
for local dev), region, explicit access keys, or a named profile — in that
order of precedence.

``invalidate_s3_client()`` clears the cache so the next call rebuilds the
client; this is how callers recover from expired temporary credentials (the
client is rebuilt to pick up refreshed credentials).

``boto3`` is imported lazily inside the builder so this module compiles without
boto3 installed.
"""
from __future__ import annotations

import threading

# Module-level S3 client cache — one client per process, thread-safe construction.
_s3_client = None
_s3_client_lock = threading.Lock()


def _build_s3_client_uncached():
    import boto3
    from botocore.config import Config

    from app.core.config import settings

    boto_config = Config(
        retries={"max_attempts": 3, "mode": "adaptive"},
        s3={"addressing_style": "path"},
    )
    kwargs: dict = {"region_name": settings.AWS_REGION, "config": boto_config}
    if settings.AWS_S3_ENDPOINT_URL:
        kwargs["endpoint_url"] = settings.AWS_S3_ENDPOINT_URL
    if settings.AWS_ACCESS_KEY_ID and settings.AWS_SECRET_ACCESS_KEY:
        kwargs["aws_access_key_id"] = settings.AWS_ACCESS_KEY_ID
        kwargs["aws_secret_access_key"] = settings.AWS_SECRET_ACCESS_KEY
        return boto3.client("s3", **kwargs)
    if settings.AWS_PROFILE:
        session = boto3.Session(profile_name=settings.AWS_PROFILE)
        return session.client("s3", **kwargs)
    return boto3.client("s3", **kwargs)


def build_s3_client():
    """Return a cached S3 client, rebuilding it on first use after invalidation."""
    global _s3_client
    if _s3_client is not None:
        return _s3_client
    with _s3_client_lock:
        if _s3_client is not None:
            return _s3_client
        _s3_client = _build_s3_client_uncached()
        return _s3_client


def invalidate_s3_client():
    """Discard the cached client — called on expired credentials so the next
    call rebuilds it with refreshed credentials."""
    global _s3_client
    with _s3_client_lock:
        _s3_client = None
