"""Alembic environment for the KB service.

Runs migrations against the ``kb`` schema only. Uses the synchronous psycopg2
driver: ``DATABASE_URL`` may carry an ``asyncpg`` prefix (the app uses the async
driver), so this env rewrites ``postgresql+asyncpg://`` → ``postgresql://``
before building the migration engine.
"""
from __future__ import annotations

import os
from logging.config import fileConfig

from alembic import context
from sqlalchemy import create_engine, pool

# ---------------------------------------------------------------------------
# Import KB models so their metadata is registered on Base.metadata.
# ---------------------------------------------------------------------------
from app.models.base import Base  # noqa: F401 — registers DeclarativeBase
import app.models  # noqa: F401 — ensures all models are imported

# ---------------------------------------------------------------------------
# Alembic Config object (alembic.ini values).
# ---------------------------------------------------------------------------
config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata


def _get_url() -> str:
    """Resolve DATABASE_URL, converting asyncpg → psycopg2 if needed."""
    url = os.environ.get("DATABASE_URL") or config.get_main_option("sqlalchemy.url", "")
    # Alembic uses the synchronous driver; swap the asyncpg dialect.
    return url.replace("postgresql+asyncpg://", "postgresql://").replace(
        "asyncpg://", "postgresql://"
    )


def run_migrations_offline() -> None:
    url = _get_url()
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        include_schemas=True,
        version_table_schema="kb",
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    connectable = create_engine(_get_url(), poolclass=pool.NullPool)
    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            include_schemas=True,
            version_table_schema="kb",
        )
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
