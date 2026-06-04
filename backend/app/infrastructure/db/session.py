"""Database connection management.

Provides a lazy-initialized SQLAlchemy async engine and session factory.
Engine lifecycle is managed by the application lifespan in main.py.
"""

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.core.config import settings


class _EngineManager:
    """Encapsulates engine state to avoid bare global mutation.

    A single instance manages the lazy-initialized engine and session factory.
    """

    def __init__(self) -> None:
        self._engine = None
        self._session_factory = None

    def get_engine(self):
        """Get or create the async engine (lazy initialization)."""
        if self._engine is None:
            self._engine = create_async_engine(settings.DATABASE_URL)
        return self._engine

    def get_session_factory(self):
        """Get or create the session factory (lazy initialization)."""
        if self._session_factory is None:
            self._session_factory = async_sessionmaker(
                self.get_engine(), class_=AsyncSession, expire_on_commit=False
            )
        return self._session_factory

    def reset(self) -> None:
        """Reset engine for testing — creates fresh connection in a new event loop."""
        self._engine = None
        self._session_factory = None

    async def cleanup(self) -> None:
        """Dispose the database engine connection pool on shutdown."""
        if self._engine is not None:
            await self._engine.dispose()
            self._engine = None
            self._session_factory = None


# Module-level singleton
_manager = _EngineManager()


def get_engine():
    """Get or create the async engine."""
    return _manager.get_engine()


def get_session_factory():
    """Get or create the session factory."""
    return _manager.get_session_factory()


async def get_db():
    """FastAPI dependency for getting a database session."""
    async with get_session_factory()() as session:
        yield session


def reset_db_engine() -> None:
    """Reset engine for testing — call this to create a fresh connection in a new event loop."""
    _manager.reset()


async def cleanup_db_engine() -> None:
    """Dispose the database engine connection pool on shutdown."""
    await _manager.cleanup()
