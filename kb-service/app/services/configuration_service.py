"""Configuration service — provision, read, and delete pipeline configs.

Holds the default parse/chunk/embed/vectorstore config applied to every new
configuration. Business logic only — all DB access is delegated to the repo.
"""
from __future__ import annotations

import uuid

import structlog
from sqlalchemy.ext.asyncio import AsyncSession

from app.repositories.configuration_repo import ConfigurationRepository
from app.schemas.configuration import ConfigurationCreate, ConfigurationResponse

logger = structlog.get_logger(__name__)

# Default pipeline config values applied to every new configuration
# (when the caller leaves the corresponding field empty).
_DEFAULT_PARSE_CONFIG: dict = {"strategy": "auto"}
_DEFAULT_CHUNK_CONFIG: dict = {
    "strategy": "token_based_recursive",
    "chunk_size_tokens": 400,
    "chunk_overlap_tokens": 40,
    "tokenizer": "cl100k_base",
}
_DEFAULT_EMBED_CONFIG: dict = {"dimensions": 1536, "model": "text-embedding-3-small"}
_DEFAULT_VECTORSTORE_CONFIG: dict = {"index_type": "hnsw", "m": 16, "ef_construction": 64}


class ConfigurationService:
    def __init__(self, session: AsyncSession) -> None:
        self._repo = ConfigurationRepository(session)

    async def create(self, data: ConfigurationCreate) -> ConfigurationResponse:
        merged = ConfigurationCreate(
            name=data.name,
            collection_name=data.collection_name,
            parse_config=data.parse_config or _DEFAULT_PARSE_CONFIG,
            chunk_config=data.chunk_config or _DEFAULT_CHUNK_CONFIG,
            embed_config=data.embed_config or _DEFAULT_EMBED_CONFIG,
            vectorstore_config=data.vectorstore_config or _DEFAULT_VECTORSTORE_CONFIG,
        )
        config = await self._repo.create(merged)
        logger.info("kb_configuration_created", config_id=str(config.id), name=config.name)
        return ConfigurationResponse.model_validate(config)

    async def get(self, config_id: uuid.UUID) -> ConfigurationResponse | None:
        config = await self._repo.get(config_id)
        if config is None:
            return None
        return ConfigurationResponse.model_validate(config)

    async def list(self, name_filter: str | None = None) -> list[ConfigurationResponse]:
        configs = await self._repo.list(name_filter=name_filter)
        return [ConfigurationResponse.model_validate(c) for c in configs]

    async def delete(self, config_id: uuid.UUID) -> None:
        await self._repo.delete(config_id)  # idempotent — no-op if not found
        logger.info("kb_configuration_deleted", config_id=str(config_id))
