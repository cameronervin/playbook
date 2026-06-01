"""Pytest configuration for backend tests."""
import os
import sys
from unittest.mock import AsyncMock
from uuid import uuid4

# Add backend to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Load environment variables before any app imports
try:
    from dotenv import load_dotenv

    load_dotenv()
except ImportError:
    pass

import pytest
import pytest_asyncio
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.core.config import settings
from app.models.base import Base


def pytest_configure(config):
    """Configure pytest markers."""
    config.addinivalue_line("markers", "slow: marks tests as slow (deselect with '-m \"not slow\"')")
    config.addinivalue_line("markers", "integration: marks tests as integration tests requiring external services")
    config.addinivalue_line("markers", "db: marks tests that require the test database")


def _get_test_database_url() -> str:
    """Resolve the test database URL, refusing to use the production database.

    Uses TEST_DATABASE_URL if set, otherwise derives a '<db>_test' database from
    DATABASE_URL so test teardown never drops tables in the live database.
    """
    explicit_url = os.getenv("TEST_DATABASE_URL")
    if explicit_url:
        return explicit_url

    prod_url = settings.DATABASE_URL
    db_name = prod_url.rsplit("/", 1)[-1] if "/" in prod_url else ""
    return prod_url.rsplit("/", 1)[0] + f"/{db_name}_test"


@pytest_asyncio.fixture(scope="function")
async def db_session():
    """Create a DB session with schema reset for test isolation.

    Skips cleanly when the test database is unavailable rather than hanging.
    """
    test_db_url = _get_test_database_url()

    engine = create_async_engine(
        test_db_url,
        echo=False,
        pool_pre_ping=True,
        connect_args={"timeout": 5},
    )

    try:
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
    except Exception as exc:
        await engine.dispose()
        pytest.skip(
            f"Test database unavailable ({exc.__class__.__name__}): "
            "create a '<db>_test' database or set TEST_DATABASE_URL."
        )

    async_session_maker = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async with async_session_maker() as session:
        yield session
        await session.rollback()

    async with engine.begin() as conn:
        await conn.execute(text("DROP SCHEMA public CASCADE"))
        await conn.execute(text("CREATE SCHEMA public"))
        await conn.execute(text("GRANT ALL ON SCHEMA public TO public"))

    await engine.dispose()


@pytest_asyncio.fixture
async def example_factory(db_session):
    """Factory for creating test Example records."""
    from app.models.example import Example

    async def create_example(**kwargs):
        defaults = {"name": f"Test Example {uuid4().hex[:8]}", "status": "active"}
        defaults.update(kwargs)
        example = Example(**defaults)
        db_session.add(example)
        await db_session.flush()
        await db_session.refresh(example)
        return example

    return create_example


@pytest.fixture
def mock_storage_provider():
    """Mock storage provider for testing uploads.

    Returns an AsyncMock with all StorageProvider methods configured for
    successful operations.
    """
    storage = AsyncMock()
    storage.upload_file = AsyncMock()
    storage.download_file = AsyncMock()
    storage.delete_file = AsyncMock()
    storage.file_exists = AsyncMock(return_value=True)
    storage.get_presigned_url = AsyncMock(return_value="https://example.com/presigned-url")
    return storage
