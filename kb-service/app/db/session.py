"""Async SQLAlchemy session management for KB service.

Threading model:
    Celery workers run with a threads pool. asyncio is strict about each thread
    owning its own event loop, and pooled asyncpg connections are bound to the
    loop active at creation. A shared module-level engine therefore breaks the
    moment a sibling thread tries to reuse a connection from a different loop
    ("Future attached to a different loop" errors).

    We solve this with **thread-local engines** + **NullPool**:
      * Each thread caches its own engine the first time it asks. Subsequent
        tasks on that thread reuse it.
      * NullPool means every session opens a fresh connection and closes it on
        exit — no pool state survives across loops.
      * Cost: ~30-50 ms per query for the connection handshake. Negligible
        compared to embedding-gateway calls and chunk staging.
"""
from __future__ import annotations

import threading
from contextlib import asynccontextmanager
from typing import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from app.core.config import settings


class _EngineManager:
    def __init__(self) -> None:
        # Thread-local storage so each pool worker thread gets its own engine.
        self._local = threading.local()

    def get_engine(self):
        engine = getattr(self._local, "engine", None)
        if engine is None:
            engine = create_async_engine(
                settings.DATABASE_URL,
                poolclass=NullPool,  # Fresh connection per session; no loop binding to worry about.
            )
            self._local.engine = engine
        return engine

    def get_session_factory(self):
        factory = getattr(self._local, "session_factory", None)
        if factory is None:
            factory = async_sessionmaker(
                self.get_engine(), class_=AsyncSession, expire_on_commit=False
            )
            self._local.session_factory = factory
        return factory

    def reset(self) -> None:
        # Per-thread reset — clears only the calling thread's cached engine.
        self._local.engine = None
        self._local.session_factory = None

    async def cleanup(self) -> None:
        engine = getattr(self._local, "engine", None)
        if engine is not None:
            await engine.dispose()
            self._local.engine = None
            self._local.session_factory = None


_manager = _EngineManager()


def get_engine():
    return _manager.get_engine()


def get_session_factory():
    return _manager.get_session_factory()


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """FastAPI dependency — yields a session bound to the request's event loop."""
    async with get_session_factory()() as session:
        yield session


@asynccontextmanager
async def worker_db_session() -> AsyncGenerator[AsyncSession, None]:
    """Context-manager session for Celery worker tasks (not a FastAPI dependency)."""
    async with get_session_factory()() as session:
        yield session


def reset_db_engine() -> None:
    _manager.reset()


async def cleanup_db_engine() -> None:
    await _manager.cleanup()
