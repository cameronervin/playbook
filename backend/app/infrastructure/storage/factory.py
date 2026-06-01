"""Storage provider factory.

Manages a lazy-initialized S3 storage provider singleton. boto3 clients are
thread-safe, so a process-lifetime singleton is appropriate.
"""

import structlog

from app.infrastructure.storage.provider import StorageProvider
from app.infrastructure.storage.s3_client import S3StorageProvider

logger = structlog.get_logger()


class _StorageManager:
    """Encapsulates storage provider state for lazy initialization."""

    def __init__(self) -> None:
        self._provider: StorageProvider | None = None

    def get_provider(self) -> StorageProvider:
        if self._provider is None:
            self._provider = S3StorageProvider()
            logger.info("Storage provider initialized")
        return self._provider

    def cleanup(self) -> None:
        """Release the boto3 client and its urllib3 connection pool."""
        if self._provider is not None:
            client = getattr(self._provider, "_client", None)
            if client is not None:
                client.close()
            self._provider = None
            logger.info("Storage provider cleaned up")

    def reset(self) -> None:
        """Reset provider for testing — creates a fresh instance on next access."""
        self._provider = None


_manager = _StorageManager()


def get_storage_provider() -> StorageProvider:
    """Factory for the storage provider (cached singleton).

    Controlled by S3_ENDPOINT_URL: set to a LocalStack URL for local dev, leave
    empty/unset for production AWS S3.
    """
    return _manager.get_provider()


def get_storage_provider_dependency() -> StorageProvider:
    """FastAPI dependency for the storage provider. Use with Depends()."""
    return get_storage_provider()


def cleanup_storage_provider() -> None:
    """Release storage resources during application shutdown."""
    _manager.cleanup()


def reset_storage_provider() -> None:
    """Reset the storage provider for testing."""
    _manager.reset()
