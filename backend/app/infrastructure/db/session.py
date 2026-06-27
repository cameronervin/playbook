"""Database connection management.

Provides a lazy-initialized SQLAlchemy async engine and session factory.
Engine lifecycle is managed by the application lifespan in main.py.
"""

from typing import Annotated

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.core.config import Settings, get_request_settings, get_settings


class _EngineManager:
    """Encapsulates engine state to avoid bare global mutation.

    A single instance manages the lazy-initialized engine and session factory.
    """

    def __init__(self) -> None:
        self._engines = {}
        self._session_factories = {}

    def get_engine(self, database_url: str):
        """Get or create the async engine (lazy initialization)."""
        if database_url not in self._engines:
            self._engines[database_url] = create_async_engine(database_url)
        return self._engines[database_url]

    def get_session_factory(self, database_url: str):
        """Get or create the session factory (lazy initialization)."""
        if database_url not in self._session_factories:
            self._session_factories[database_url] = async_sessionmaker(
                self.get_engine(database_url), class_=AsyncSession, expire_on_commit=False
            )
        return self._session_factories[database_url]

    def reset(self) -> None:
        """Reset engine for testing — creates fresh connection in a new event loop."""
        self._engines = {}
        self._session_factories = {}

    async def cleanup(self) -> None:
        """Dispose the database engine connection pool on shutdown."""
        for engine in self._engines.values():
            await engine.dispose()
        self.reset()


# Module-level singleton
_manager = _EngineManager()


def get_engine(app_settings: Settings | None = None):
    """Get or create the async engine."""
    resolved = app_settings or get_settings()
    return _manager.get_engine(resolved.DATABASE_URL)


def get_session_factory(app_settings: Settings | None = None):
    """Get or create the session factory."""
    resolved = app_settings or get_settings()
    return _manager.get_session_factory(resolved.DATABASE_URL)


async def get_db(
    app_settings: Annotated[Settings, Depends(get_request_settings)],
):
    """FastAPI dependency for getting a database session."""
    async with get_session_factory(app_settings)() as session:
        yield session


def reset_db_engine() -> None:
    """Reset engine for testing — call this to create a fresh connection in a new event loop."""
    _manager.reset()


async def cleanup_db_engine() -> None:
    """Dispose the database engine connection pool on shutdown."""
    await _manager.cleanup()
