"""Celery ingestion pipeline dispatch helper."""

from __future__ import annotations

import uuid
from typing import Any, Protocol

from app.repositories.ingestion_log_repo import IngestionLogRepository


class _ConfigurationWithId(Protocol):
    id: uuid.UUID


class IngestionPipelineDispatcher:
    def __init__(self, log_repo: IngestionLogRepository) -> None:
        self._log_repo = log_repo

    async def dispatch(
        self,
        document_id: uuid.UUID,
        config: _ConfigurationWithId,
        s3_key: str,
        filename: str,
        metadata: dict[str, Any],
    ) -> str:
        # Lazy import: worker task modules pull in Celery and provider setup.
        from app.workers.tasks import chunk_task, embed_task, parse_task, summarize_task

        pipeline = parse_task.s(
            document_id=str(document_id),
            s3_key=s3_key,
            filename=filename,
            config_id=str(config.id),
        ) | chunk_task.s(
            document_id=str(document_id),
            metadata=metadata,
        ) | summarize_task.s(
            document_id=str(document_id),
        ) | embed_task.s(
            document_id=str(document_id),
            config_id=str(config.id),
        )
        result = pipeline.apply_async()
        pipeline_task_id = result.id
        await self._log_repo.set_root_task_id(document_id, pipeline_task_id)
        return pipeline_task_id
