"""Lightweight summary generation task for the KB ingestion pipeline."""
from __future__ import annotations

import asyncio
import time
import uuid
from typing import Any

import structlog

from app.services.summary_service import (
    SummarySource,
    fallback_summary,
    summarize_source,
)
from app.workers.app import kb_worker
from app.workers.tasks.staging import _load_chunk_indices_from_s3

logger = structlog.get_logger(__name__)

_DEFAULT_SUMMARY_CHUNK_SAMPLE = 12


@kb_worker.task(bind=True, name="app.workers.tasks.summarize_task", max_retries=0)
def summarize_task(self, prev: dict, *, document_id: str) -> dict:
    """Generate and persist a canonical source summary without blocking ingest."""
    from app.infrastructure.db.session import get_session_factory
    from app.repositories.document_repo import DocumentRepository
    from app.repositories.ingestion_log_repo import IngestionLogRepository
    from app.workers.app import run_async

    document_uuid = uuid.UUID(document_id)
    chunk_count = prev.get("chunk_count", 0) if isinstance(prev, dict) else 0
    start = time.perf_counter()

    async def _run() -> dict:
        session_factory = get_session_factory()
        async with session_factory() as session:
            doc_repo = DocumentRepository(session)
            log_repo = IngestionLogRepository(session)
            document = await doc_repo.get(document_uuid)
            log = await log_repo.get_by_document(document_uuid)
            if document is None:
                return {**_prev_dict(prev), "summary": None}
            await log_repo.update_stage(
                document.id,
                stage="summarize",
                task_id=self.request.id if self.request else None,
                status="STARTED",
            )

            chunks = await asyncio.to_thread(
                _load_summary_chunks,
                document_id,
                chunk_count,
            )
            source = _summary_source_from_document(
                document=document,
                parse_result=log.parse_result if log else None,
                chunks=chunks,
            )
            try:
                summary = await summarize_source(source)
            except Exception as exc:  # pragma: no cover - summarize_source catches agent errors.
                logger.warning(
                    "kb_summary_unexpected_failure_using_fallback",
                    document_id=document_id,
                    error_type=type(exc).__name__,
                )
                summary = fallback_summary(source)

            await doc_repo.update_summary(document.id, summary)
            await log_repo.update_stage(
                document.id,
                stage="summarize",
                status="SUCCESS",
            )
            elapsed_ms = int((time.perf_counter() - start) * 1000)
            logger.info(
                "kb_summary_completed",
                document_id=document_id,
                source_type=(document.metadata_ or {}).get("source_type"),
                chunk_count=chunk_count,
                elapsed_ms=elapsed_ms,
            )
            return {**_prev_dict(prev), "summary": summary}

    return run_async(_run())


def _load_summary_chunks(document_id: str, chunk_count: int) -> list[dict[str, Any]]:
    indices = _select_summary_indices(chunk_count, max_chunks=_DEFAULT_SUMMARY_CHUNK_SAMPLE)
    if not indices:
        return []
    return _load_chunk_indices_from_s3(document_id, indices)


def _select_summary_indices(chunk_count: int, *, max_chunks: int) -> list[int]:
    """Pick early and representative chunk indices deterministically."""
    if chunk_count <= 0 or max_chunks <= 0:
        return []
    if chunk_count <= max_chunks:
        return list(range(chunk_count))
    if max_chunks == 1:
        return [0]
    selected = list(range(min(3, max_chunks, chunk_count)))
    remaining = max_chunks - len(selected)
    for position in range(remaining):
        index = round((position + 1) * (chunk_count - 1) / remaining)
        if index not in selected:
            selected.append(index)
    return sorted(selected)[:max_chunks]


def _summary_source_from_document(
    *,
    document: Any,
    parse_result: dict[str, Any] | None,
    chunks: list[dict[str, Any]],
) -> SummarySource:
    metadata = dict(document.metadata_ or {})
    return SummarySource(
        filename=str(document.name),
        source_title=metadata.get("source_title") or str(document.name),
        metadata=metadata,
        parse_result=parse_result or {},
        chunks=chunks,
    )


def _prev_dict(prev: dict | None) -> dict:
    return dict(prev) if isinstance(prev, dict) else {}
