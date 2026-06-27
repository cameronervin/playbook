"""Storage provider factory.

Manages a lazy-initialized S3 storage provider singleton. boto3 clients are
thread-safe, so a process-lifetime singleton is appropriate.
"""

from typing import Annotated

import structlog
from fastapi import Depends

from app.core.config import Settings, get_request_settings, get_settings
from app.infrastructure.storage.provider import StorageProvider
from app.infrastructure.storage.s3_client import S3StorageProvider

logger = structlog.get_logger()


class _StorageManager:
    """Encapsulates storage provider state for lazy initialization."""

    def __init__(self) -> None:
        self._providers: dict[str, StorageProvider] = {}

    def get_provider(self, settings: Settings) -> StorageProvider:
        cache_key = settings.model_dump_json()
        if cache_key not in self._providers:
            self._providers[cache_key] = S3StorageProvider(settings)
            logger.info("Storage provider initialized")
        return self._providers[cache_key]

    def cleanup(self) -> None:
        """Release the boto3 client and its urllib3 connection pool."""
        for provider in self._providers.values():
            client = getattr(provider, "_client", None)
            if client is not None:
                client.close()
        if self._providers:
            logger.info("Storage provider cleaned up")
        self._providers = {}

    def reset(self) -> None:
        """Reset provider for testing — creates a fresh instance on next access."""
        self._providers = {}


_manager = _StorageManager()


def get_storage_provider(app_settings: Settings | None = None) -> StorageProvider:
    """Factory for the storage provider (cached singleton).

    Controlled by S3_ENDPOINT_URL: set to a MinIO URL for local dev, leave
    empty/unset for production AWS S3.
    """
    return _manager.get_provider(app_settings or get_settings())


def get_storage_provider_dependency(
    app_settings: Annotated[Settings, Depends(get_request_settings)],
) -> StorageProvider:
    """FastAPI dependency for the storage provider. Use with Depends()."""
    return get_storage_provider(app_settings)


def cleanup_storage_provider() -> None:
    """Release storage resources during application shutdown."""
    _manager.cleanup()


def reset_storage_provider() -> None:
    """Reset the storage provider for testing."""
    _manager.reset()
