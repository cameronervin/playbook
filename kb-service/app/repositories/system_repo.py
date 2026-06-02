"""Repository for low-level system probes."""
from __future__ import annotations

import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncEngine

logger = structlog.get_logger(__name__)


class SystemRepository:
    def __init__(self, engine: AsyncEngine) -> None:
        self._engine = engine

    async def ping_db(self) -> None:
        """Execute a trivial SELECT to confirm Postgres is reachable."""
        async with self._engine.connect() as conn:
            await conn.execute(select(1))
