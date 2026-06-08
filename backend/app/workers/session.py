"""Worker database session management.

Background workers (e.g. Celery) are long-lived processes that don't use
FastAPI's Depends() dependency injection. This module provides an async session
context manager workers can use to get their own DB sessions, independent of any
HTTP request lifecycle.

Note: do NOT wrap with session.begin() — repository methods call
session.commit() explicitly, so each method manages its own transaction.
"""

from contextlib import asynccontextmanager

from app.infrastructure.db.session import get_session_factory


@asynccontextmanager
async def worker_db_session():
    """Async context manager yielding a fresh DB session for a worker task.

    Usage::

        async with worker_db_session() as session:
            repo = SomeRepository(session=session)
            await repo.create({...})
    """
    session_factory = get_session_factory()
    async with session_factory() as session:
        yield session
