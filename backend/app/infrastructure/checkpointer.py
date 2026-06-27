"""LangGraph checkpointer infrastructure.

Provides connection-pool and checkpointer creation for LangGraph state
persistence. Lifecycle is owned by the main.py lifespan.
"""

import datetime

import structlog
from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
from psycopg.rows import dict_row
from psycopg_pool import AsyncConnectionPool

from app.core.config import Settings, get_settings

logger = structlog.get_logger(__name__)


def _convert_to_psycopg_dsn(db_url: str) -> str:
    """Convert a SQLAlchemy URL to a psycopg DSN.

    SQLAlchemy uses: postgresql+asyncpg://user:pass@host:port/db
    psycopg needs:   postgresql://user:pass@host:port/db
    """
    if "+asyncpg" in db_url:
        db_url = db_url.replace("+asyncpg", "")
    return db_url


async def create_checkpointer_pool(
    app_settings: Settings | None = None,
) -> AsyncConnectionPool:
    """Create and open the async connection pool for the LangGraph checkpointer."""
    settings = app_settings or get_settings()
    db_url = settings.LANGGRAPH_CHECKPOINT_DB_URL or settings.DATABASE_URL
    psycopg_url = _convert_to_psycopg_dsn(db_url)

    pool = AsyncConnectionPool(
        conninfo=psycopg_url,
        min_size=1,
        max_size=10,
        open=False,
        kwargs={"autocommit": True, "row_factory": dict_row, "prepare_threshold": 0},
    )
    await pool.open()
    return pool


async def create_checkpointer(pool: AsyncConnectionPool) -> AsyncPostgresSaver:
    """Create and set up the checkpointer with the given pool (initializes tables)."""
    checkpointer = AsyncPostgresSaver(pool)
    await checkpointer.setup()
    return checkpointer


async def cleanup_checkpointer_pool(pool: AsyncConnectionPool | None) -> None:
    """Close the checkpointer connection pool. Safe to call with None."""
    if pool is not None:
        await pool.close()


async def prune_old_checkpoints(
    pool: AsyncConnectionPool,
    days: int | None = None,
    app_settings: Settings | None = None,
) -> int:
    """Delete LangGraph checkpoint data older than *days* days.

    Removes rows from ``langgraph_checkpoint_writes`` and ``langgraph_checkpoints``
    older than the retention window. Returns the total number of rows deleted.
    """
    settings = app_settings or get_settings()
    retention_days = days if days is not None else settings.CHECKPOINT_RETENTION_DAYS
    cutoff = datetime.datetime.now(tz=datetime.timezone.utc) - datetime.timedelta(days=retention_days)

    async with pool.connection() as conn:
        result = await conn.execute(
            """
            DELETE FROM langgraph_checkpoint_writes
            WHERE thread_id IN (
                SELECT thread_id FROM langgraph_checkpoints
                WHERE created_at < %s
            )
            """,
            (cutoff,),
        )
        deleted_writes = result.rowcount or 0

        result = await conn.execute(
            "DELETE FROM langgraph_checkpoints WHERE created_at < %s",
            (cutoff,),
        )
        deleted_checkpoints = result.rowcount or 0

    deleted_total = deleted_writes + deleted_checkpoints
    logger.info(
        "Checkpoint pruning completed",
        cutoff=cutoff.isoformat(),
        retention_days=retention_days,
        deleted_writes=deleted_writes,
        deleted_checkpoints=deleted_checkpoints,
    )
    return deleted_total
