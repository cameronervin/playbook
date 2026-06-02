"""Repository for kb.configurations CRUD.

All DB access for configurations goes through here (Repository pattern):
services orchestrate, repositories own the SQLAlchemy ``select()``/``commit()``.
"""
from __future__ import annotations

import uuid

import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.configuration import Configuration
from app.schemas.configuration import ConfigurationCreate

logger = structlog.get_logger(__name__)


class ConfigurationRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create(self, data: ConfigurationCreate) -> Configuration:
        config = Configuration(
            name=data.name,
            collection_name=data.collection_name,
            parse_config=data.parse_config,
            chunk_config=data.chunk_config,
            embed_config=data.embed_config,
            vectorstore_config=data.vectorstore_config,
        )
        self._session.add(config)
        await self._session.commit()
        await self._session.refresh(config)
        return config

    async def get(self, config_id: uuid.UUID) -> Configuration | None:
        result = await self._session.execute(
            select(Configuration).where(Configuration.id == config_id)
        )
        return result.scalar_one_or_none()

    async def get_by_name(self, name: str) -> Configuration | None:
        result = await self._session.execute(
            select(Configuration).where(Configuration.name == name)
        )
        return result.scalar_one_or_none()

    async def list(self, name_filter: str | None = None) -> list[Configuration]:
        stmt = select(Configuration)
        if name_filter:
            stmt = stmt.where(Configuration.name == name_filter)
        result = await self._session.execute(stmt)
        return list(result.scalars().all())

    async def delete(self, config_id: uuid.UUID) -> None:
        config = await self.get(config_id)
        if config:
            await self._session.delete(config)
            await self._session.commit()
