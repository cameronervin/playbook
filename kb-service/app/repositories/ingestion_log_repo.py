"""Repository for kb.ingestion_logs CRUD."""
from __future__ import annotations

import uuid
from datetime import datetime

import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.ingestion_log import IngestionLog

logger = structlog.get_logger(__name__)


class IngestionLogRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create(self, document_id: uuid.UUID) -> IngestionLog:
        log = IngestionLog(document_id=document_id)
        self._session.add(log)
        await self._session.commit()
        await self._session.refresh(log)
        return log

    async def set_parse_result(
        self,
        document_id: uuid.UUID,
        *,
        selected_parser: str,
        route: str,
        reason_codes: list[str],
        quality_signals: dict,
        artifacts: dict | None = None,
        artifact_summary: dict | None = None,
        text_segment_count: int | None = None,
        warnings: list[str] | None = None,
    ) -> IngestionLog | None:
        log = await self.get_by_document(document_id)
        if not log:
            return None
        payload = {
            "selected_parser": selected_parser,
            "route": route,
            "reason_codes": reason_codes,
            "quality_signals": quality_signals,
            "artifacts": artifacts or {},
            "artifact_summary": artifact_summary or {},
            "text_segment_count": text_segment_count or 0,
            "warnings": warnings or [],
        }
        setattr(log, "parse_result", payload)
        log.updated_at = datetime.utcnow()
        await self._session.commit()
        await self._session.refresh(log)
        return log

    async def get_by_document(self, document_id: uuid.UUID) -> IngestionLog | None:
        result = await self._session.execute(
            select(IngestionLog).where(IngestionLog.document_id == document_id)
        )
        return result.scalar_one_or_none()

    async def set_root_task_id(self, document_id: uuid.UUID, root_task_id: str) -> IngestionLog | None:
        log = await self.get_by_document(document_id)
        if not log:
            return None
        setattr(log, "pipeline_task_id", root_task_id)
        log.updated_at = datetime.utcnow()
        await self._session.commit()
        await self._session.refresh(log)
        return log

    async def get_by_any_task_id(self, task_id: str) -> IngestionLog | None:
        """Match against the root pipeline task id or any per-stage task id."""
        result = await self._session.execute(
            select(IngestionLog).where(
                (IngestionLog.pipeline_task_id == task_id)
                | (IngestionLog.parse_task_id == task_id)
                | (IngestionLog.chunk_task_id == task_id)
                | (IngestionLog.embed_task_id == task_id)
                | (IngestionLog.load_vector_task_id == task_id)
            )
        )
        return result.scalar_one_or_none()

    async def update_stage(
        self,
        document_id: uuid.UUID,
        *,
        stage: str,
        task_id: str | None = None,
        status: str,
        error_message: str | None = None,
    ) -> IngestionLog | None:
        log = await self.get_by_document(document_id)
        if not log:
            return None
        if task_id:
            setattr(log, f"{stage}_task_id", task_id)
        setattr(log, f"{stage}_status", status)
        if error_message:
            log.error_message = error_message
        log.updated_at = datetime.utcnow()
        await self._session.commit()
        await self._session.refresh(log)
        return log
