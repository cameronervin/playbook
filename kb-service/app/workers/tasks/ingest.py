"""Parse and chunk Celery tasks for the KB ingestion pipeline."""
from __future__ import annotations

import asyncio
import time
import uuid

import structlog
from celery.exceptions import SoftTimeLimitExceeded

from app.workers.app import kb_worker
from app.workers.tasks.notify import _notify
from app.workers.tasks.staging import (
    _delete_pages_staging,
    _delete_staging_file,
    _iter_pages_from_s3,
    _save_chunks_to_s3,
    _save_pages_to_s3,
    _staging_key,
)
from app.workers.tasks.text_validation import _ensure_parse_outcome_has_usable_text

logger = structlog.get_logger(__name__)

# ---------------------------------------------------------------------------
# parse_task — first stage of the chain. Keyword-only signature matches
# ingestion_service._dispatch_pipeline's parse_task.s(...) call.
# ---------------------------------------------------------------------------
@kb_worker.task(bind=True, name="app.workers.tasks.parse_task", max_retries=3)
def parse_task(
    self,
    *,
    document_id: str,
    s3_key: str,
    filename: str,
    config_id: str,
) -> dict:
    """Parse a document, stage page text to S3, return a lightweight summary dict.

    Pages are written to ``kb/staging/{doc_id}/pages.ndjson`` and chunk_task
    streams them back — so MBs of text never travel through the Redis broker.
    """
    from app.core.config import settings
    from app.infrastructure.db.session import get_session_factory
    from app.infrastructure.io.s3_tempfile import stream_s3_object_to_tempfile
    from app.infrastructure.parsers.contracts.errors import (
        CorruptFileError,
        NoTextExtractedError,
        OCRTimeoutError,
        ParseWarning,
    )
    from app.repositories.document_repo import DocumentRepository
    from app.repositories.ingestion_log_repo import IngestionLogRepository
    from app.workers.app import run_async

    document_uuid = uuid.UUID(document_id)
    logger.info(
        "kb_parse_started",
        document_id=document_uuid,
        s3_key=s3_key,
        filename=filename,
        config_id=config_id,
    )

    async def _run() -> dict:
        session_factory = get_session_factory()
        async with session_factory() as session:
            doc_repo = DocumentRepository(session)
            log_repo = IngestionLogRepository(session)

            doc = await doc_repo.get(document_uuid)
            if doc:
                await doc_repo.update_status(doc.id, "parsing")
                await log_repo.update_stage(
                    doc.id,
                    stage="parse",
                    task_id=self.request.id if self.request else None,
                    status="STARTED",
                )
                _notify(document_id, "parse", "STARTED")

            try:
                from app.workers.state import worker_state

                router = worker_state.parser_router
                if router is None:
                    from app.infrastructure.parsers.routing.router import ParserRouter

                    worker_state.parser_router = ParserRouter()
                    router = worker_state.parser_router
                async with stream_s3_object_to_tempfile(
                    bucket=settings.S3_BUCKET_NAME,
                    s3_key=s3_key,
                    suffix=f".{filename.rsplit('.', maxsplit=1)[-1].lower()}"
                    if "." in filename
                    else "",
                ) as tmp_path:
                    outcome = await router.route_path(
                        path=tmp_path,
                        filename=filename,
                        s3_bucket=settings.S3_BUCKET_NAME,
                        s3_key=s3_key,
                    )
            except ParseWarning as exc:
                no_text_error = NoTextExtractedError(
                    stage="parse",
                    filename=filename,
                    detail=str(exc),
                )
                if doc:
                    await doc_repo.update_status(doc.id, "failed")
                    await log_repo.update_stage(
                        doc.id,
                        stage="parse",
                        status="FAILURE",
                        error_message=str(no_text_error),
                    )
                    _notify(document_id, "parse", "FAILURE", str(no_text_error))
                logger.info(
                    "kb_no_text_extracted",
                    document_id=document_uuid,
                    stage="parse",
                    error_code=no_text_error.code,
                    filename=filename,
                )
                raise no_text_error from exc
            except (OCRTimeoutError, TimeoutError, SoftTimeLimitExceeded) as exc:
                if doc:
                    await log_repo.update_stage(
                        doc.id, stage="parse", status="FAILURE", error_message=str(exc)
                    )
                    _notify(document_id, "parse", "FAILURE", str(exc))
                raise self.retry(exc=exc) from exc
            except CorruptFileError as exc:
                if doc:
                    await doc_repo.update_status(doc.id, "failed")
                    await log_repo.update_stage(
                        doc.id, stage="parse", status="FAILURE", error_message=str(exc)
                    )
                    _notify(document_id, "parse", "FAILURE", str(exc))
                raise
            except Exception as exc:
                if doc:
                    await doc_repo.update_status(doc.id, "failed")
                    await log_repo.update_stage(
                        doc.id, stage="parse", status="FAILURE", error_message=str(exc)
                    )
                    _notify(document_id, "parse", "FAILURE", str(exc))
                raise

            try:
                _ensure_parse_outcome_has_usable_text(outcome, filename=filename)
            except NoTextExtractedError as exc:
                if doc:
                    await doc_repo.update_status(doc.id, "failed")
                    await log_repo.update_stage(
                        doc.id,
                        stage="parse",
                        status="FAILURE",
                        error_message=str(exc),
                    )
                    _notify(document_id, "parse", "FAILURE", str(exc))
                logger.info(
                    "kb_no_text_extracted",
                    document_id=document_uuid,
                    stage="parse",
                    error_code=exc.code,
                    filename=filename,
                    selected_parser=outcome.selected_parser,
                    route=outcome.route,
                    text_segment_count=len(outcome.text_segments),
                )
                raise

            # Stage pages to S3 so they don't travel through the broker.
            page_count = len(outcome.pages)
            pages_key = await asyncio.to_thread(_save_pages_to_s3, document_id, outcome.pages)

            if doc:
                await log_repo.set_parse_result(
                    doc.id,
                    selected_parser=outcome.selected_parser,
                    route=outcome.route,
                    reason_codes=outcome.reason_codes,
                    quality_signals=outcome.quality_signals,
                    artifacts=outcome.artifacts.to_dict(),
                    artifact_summary=outcome.artifacts.summary(),
                    text_segment_count=len(outcome.text_segments),
                    warnings=outcome.warnings,
                )
                await log_repo.update_stage(doc.id, stage="parse", status="SUCCESS")
                _notify(document_id, "parse", "SUCCESS")

            logger.info(
                "kb_parse_completed",
                document_id=document_uuid,
                selected_parser=outcome.selected_parser,
                route=outcome.route,
                pages=page_count,
            )
            return {
                "page_count": page_count,
                "pages_s3_key": pages_key,
                "selected_parser": outcome.selected_parser,
                "route": outcome.route,
            }

    return run_async(_run())


# ---------------------------------------------------------------------------
# chunk_task — receives parse_task's result dict as the chain `prev` arg.
# ---------------------------------------------------------------------------
@kb_worker.task(bind=True, name="app.workers.tasks.chunk_task", max_retries=3)
def chunk_task(self, prev: dict, *, document_id: str, metadata: dict) -> dict:
    """Stream pages from S3 → chunker → S3 chunk staging.

    ``prev`` is the lightweight dict from parse_task (Celery passes the previous
    task's result as the first positional arg of a chain step). Pages are read
    lazily from ``kb/staging/{doc_id}/pages.ndjson``, fed into the streaming
    chunker, and the chunks are immediately written to
    ``kb/staging/{doc_id}/chunks.ndjson`` as NDJSON without ever materialising
    either the full pages list or the full chunks list in memory.
    """
    from app.infrastructure.chunkers.token_based import iter_chunks_from_pages
    from app.infrastructure.db.session import get_session_factory
    from app.infrastructure.parsers.contracts.errors import NoTextExtractedError
    from app.repositories.document_repo import DocumentRepository
    from app.repositories.ingestion_log_repo import IngestionLogRepository
    from app.workers.app import run_async

    document_uuid = uuid.UUID(document_id)
    metadata_payload = {
        **(metadata if isinstance(metadata, dict) else {}),
        "document_id": document_id,
    }
    start = time.perf_counter()

    page_count = prev.get("page_count", 0) if isinstance(prev, dict) else 0
    logger.info("kb_chunk_started", document_id=document_uuid, page_count=page_count)

    async def _run() -> dict:
        session_factory = get_session_factory()
        async with session_factory() as session:
            doc_repo = DocumentRepository(session)
            log_repo = IngestionLogRepository(session)

            doc = await doc_repo.get(document_uuid)
            if doc:
                await doc_repo.update_status(doc.id, "chunking")
                await log_repo.update_stage(
                    doc.id,
                    stage="chunk",
                    task_id=self.request.id if self.request else None,
                    status="STARTED",
                )
                _notify(document_id, "chunk", "STARTED")

            chunk_count = 0
            try:
                # Run chunking + upload in one worker thread so we can stream
                # the page iterator straight into the chunker without holding
                # the chunks list, and so SQLAlchemy stays off the event loop.
                def _run_chunk_and_stage() -> int:
                    pages_iter = _iter_pages_from_s3(document_id)
                    chunks_iter = iter_chunks_from_pages(pages_iter, metadata_payload)
                    count_box = {"n": 0}

                    def _counting():
                        for c in chunks_iter:
                            count_box["n"] += 1
                            yield c

                    _save_chunks_to_s3(document_id, _counting())
                    return count_box["n"]

                chunk_count = await asyncio.to_thread(_run_chunk_and_stage)
            except (SoftTimeLimitExceeded, TimeoutError) as exc:
                if doc:
                    await log_repo.update_stage(
                        doc.id, stage="chunk", status="FAILURE", error_message=str(exc)
                    )
                    _notify(document_id, "chunk", "FAILURE", str(exc))
                raise self.retry(exc=exc) from exc
            except Exception as exc:
                if doc:
                    await doc_repo.update_status(doc.id, "failed")
                    await log_repo.update_stage(
                        doc.id, stage="chunk", status="FAILURE", error_message=str(exc)
                    )
                    _notify(document_id, "chunk", "FAILURE", str(exc))
                raise

            if chunk_count == 0:
                no_text_error = NoTextExtractedError(stage="chunk")
                await asyncio.to_thread(_delete_pages_staging, document_id)
                await asyncio.to_thread(_delete_staging_file, document_id)
                if doc:
                    await doc_repo.update_status(doc.id, "failed")
                    await log_repo.update_stage(
                        doc.id,
                        stage="chunk",
                        status="FAILURE",
                        error_message=str(no_text_error),
                    )
                    _notify(document_id, "chunk", "FAILURE", str(no_text_error))
                    _notify(document_id, "pipeline", "failed", str(no_text_error))
                logger.info(
                    "kb_no_text_extracted",
                    document_id=document_uuid,
                    stage="chunk",
                    page_count=page_count,
                    chunk_count=chunk_count,
                    error_code=no_text_error.code,
                )
                raise no_text_error

            # Pages staging is no longer needed once chunks are written.
            await asyncio.to_thread(_delete_pages_staging, document_id)

            if doc:
                await log_repo.update_stage(doc.id, stage="chunk", status="SUCCESS")
                _notify(document_id, "chunk", "SUCCESS")

            elapsed_ms = int((time.perf_counter() - start) * 1000)
            logger.info(
                "kb_chunk_completed",
                document_id=document_uuid,
                page_count=page_count,
                chunk_count=chunk_count,
                elapsed_ms=elapsed_ms,
            )
            return {"chunk_count": chunk_count, "chunks_s3_key": _staging_key(document_id)}

    return run_async(_run())


# ---------------------------------------------------------------------------
