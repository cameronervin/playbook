"""Pytest configuration for backend tests."""
from collections.abc import AsyncGenerator
from dataclasses import dataclass
import os
import sys
from unittest.mock import AsyncMock

# Add backend to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest
import pytest_asyncio
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.core.config import Settings, set_settings_override

TEST_SETTINGS = Settings(
    _env_file=None,
    ENVIRONMENT="test",
    DEBUG=False,
    LOG_LEVEL="WARNING",
    DEV_AUTH_ENABLED=False,
    DATABASE_URL=os.getenv(
        "DATABASE_URL",
        "postgresql+asyncpg://app:localpass@localhost:5433/playbook",
    ),
    SECRET_KEY="test-secret-value-that-is-long-enough",
    OAUTH_STATE_SECRET="test-oauth-secret-value-that-is-long-enough",
    LLM_PROVIDER_MODE="direct",
    LLM_DIRECT_PROVIDER="anthropic",
    ANTHROPIC_API_KEY="test-anthropic-key",
)
set_settings_override(TEST_SETTINGS)

from app.auth.dependencies import current_active_user
from app.infrastructure.db.session import get_db
from app.main import create_app
from app.models.base import Base
from app.models.identity import User


def pytest_configure(config):
    """Configure pytest markers."""
    config.addinivalue_line("markers", "slow: marks tests as slow (deselect with '-m \"not slow\"')")
    config.addinivalue_line("markers", "integration: marks tests as integration tests requiring external services")
    config.addinivalue_line("markers", "db: marks tests that require the test database")


@pytest.fixture
def test_settings() -> Settings:
    """Return the deterministic settings object installed for tests."""
    return TEST_SETTINGS


def _get_test_database_url() -> str:
    """Resolve the test database URL, refusing to use the production database.

    Uses TEST_DATABASE_URL if set, otherwise derives a '<db>_test' database from
    DATABASE_URL so test teardown never drops tables in the live database.
    """
    explicit_url = os.getenv("TEST_DATABASE_URL")
    if explicit_url:
        return explicit_url

    prod_url = TEST_SETTINGS.DATABASE_URL
    if prod_url.startswith("postgresql://"):
        prod_url = prod_url.replace("postgresql://", "postgresql+asyncpg://", 1)
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


@dataclass
class RouteTestHarness:
    """Small wrapper for route-level tests using FastAPI dependency overrides."""

    app: FastAPI
    client: AsyncClient

    def authenticate_as(self, user: User) -> None:
        """Override the current-user dependency for role-gated routes."""

        async def override_current_active_user() -> User:
            return user

        self.app.dependency_overrides[current_active_user] = override_current_active_user


@pytest_asyncio.fixture(scope="function")
async def route_client(db_session: AsyncSession) -> AsyncGenerator[RouteTestHarness, None]:
    """Create an ASGI test client wired to the function-scoped DB session."""
    app = create_app(app_settings=TEST_SETTINGS)

    async def override_get_db() -> AsyncGenerator[AsyncSession, None]:
        yield db_session

    app.dependency_overrides[get_db] = override_get_db
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        yield RouteTestHarness(app=app, client=client)

    app.dependency_overrides = {}
