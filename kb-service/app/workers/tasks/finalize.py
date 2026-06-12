"""Load-vector finalization and recovery helpers for the KB pipeline."""
from __future__ import annotations

import asyncio
import time
import uuid

import structlog

from app.workers.app import kb_worker
from app.workers.tasks.notify import _notify
from app.workers.tasks.progress import get_embed_progress, reset_embed_progress
from app.workers.tasks.staging import _count_chunks_in_s3, _delete_staging_file

logger = structlog.get_logger(__name__)

# ---------------------------------------------------------------------------
# Reissue-missing-batches recovery — for the case where some embed_batch_task
# instances exhausted retries (e.g. extended LiteLLM outage). load_vector_task
# detects a vec-count mismatch, identifies missing chunk indices via DB query,
# and re-dispatches them as fresh batches. Bounded by MAX_REISSUE_ATTEMPTS.
# ---------------------------------------------------------------------------
_MAX_REISSUE_ATTEMPTS = 2
_REISSUE_WAIT_SECONDS = 120  # Time we wait between reissue + next load_vector check


def _group_contiguous_ranges(indices: list[int]) -> list[tuple[int, int]]:
    """Collapse a sorted index list into (start, end_inclusive) contiguous ranges.

    Example: [5, 6, 7, 15, 16, 100] → [(5, 7), (15, 16), (100, 100)]

    Used by ``_reissue_missing_chunks`` to preserve chunk_index contiguity
    required by VectorRepository's range-based idempotent DELETE+INSERT.
    """
    if not indices:
        return []
    ranges: list[tuple[int, int]] = []
    start = indices[0]
    prev = start
    for idx in indices[1:]:
        if idx == prev + 1:
            prev = idx
            continue
        ranges.append((start, prev))
        start = idx
        prev = idx
    ranges.append((start, prev))
    return ranges


def _reissue_missing_chunks(document_id: str, config_id: str) -> int:
    """Detect chunks missing from pgvector and re-dispatch them as proper batches.

    Returns the number of chunks reissued (0 if nothing missing).

    Batched (not 1-chunk-per-task) so we don't 460× amplify the queue and
    saturate LiteLLM with 429s during recovery. Reissued batches are sent
    with ``total_batches=0`` so their counter increment does NOT trigger another
    load_vector dispatch — load_vector reschedules itself via ``self.retry()``.
    """
    from app.repositories.vector_repo import VectorRepository
    from app.workers.state import worker_state
    from app.workers.tasks.embedding import embed_batch_task

    document_uuid = uuid.UUID(document_id)
    total_chunks = _count_chunks_in_s3(document_id)
    if total_chunks <= 0:
        return 0

    vector_repo = VectorRepository(worker_state.pg_engine)
    existing_indices = vector_repo.get_existing_chunk_indices(document_uuid)
    missing_indices = sorted(set(range(total_chunks)) - existing_indices)

    if not missing_indices:
        return 0

    ranges = _group_contiguous_ranges(missing_indices)
    logger.info(
        "kb_reissue_missing_batches",
        document_id=document_id,
        missing_count=len(missing_indices),
        contiguous_ranges=len(ranges),
        first_missing=missing_indices[:10],
        total_chunks=total_chunks,
    )

    # For each contiguous range, re-dispatch an embed_batch over that index
    # window. embed_batch reads the slice from S3 and writes at chunk_start + i.
    batches_dispatched = 0
    for range_start, range_end in ranges:
        embed_batch_task.apply_async(
            kwargs={
                "document_id": document_id,
                "config_id": config_id,
                "batch_index": range_start,
                "chunk_start": range_start,
                "chunk_end": range_end + 1,
                "total_batches": 0,  # sentinel — don't auto-dispatch load_vector
            }
        )
        batches_dispatched += 1

    logger.info(
        "kb_reissue_dispatched",
        document_id=document_id,
        batches_dispatched=batches_dispatched,
        chunks_reissued=len(missing_indices),
    )
    return len(missing_indices)


_MAX_DEFER_ATTEMPTS = 5  # 5 × 120s = 10 min defer budget before forcing verify+reissue


# ---------------------------------------------------------------------------
# load_vector_task — finalizer; runs on the kb-io queue.
# ---------------------------------------------------------------------------
@kb_worker.task(bind=True, name="app.workers.tasks.load_vector_task", max_retries=30)
def load_vector_task(
    self,
    *,
    document_id: str,
    config_id: str,
    reissue_attempt: int = 0,
    expected_total_batches: int = 0,
    defer_attempt: int = 0,
) -> dict:
    """Finalize a document after all embed batches have written their vectors.

    Vectors are already in pgvector — ``embed_batch_task`` writes them directly.
    This task:
      1. Early-exits if the doc is already finalised (idempotency).
      2. Smart-defers via self.retry() if embed batches are still in flight
         (progress counter < expected_total_batches).
      3. Verifies the vec count matches the staged chunk count.
      4. If short, reissues only the missing chunks (bounded passes).
      5. If matched, marks embed + load_vector + pipeline SUCCESS, notifies,
         and deletes S3 staging.
    """
    from app.infrastructure.db.session import get_session_factory
    from app.repositories.document_repo import DocumentRepository
    from app.repositories.ingestion_log_repo import IngestionLogRepository
    from app.repositories.vector_repo import VectorRepository
    from app.workers.app import run_async
    from app.workers.state import worker_state

    document_uuid = uuid.UUID(document_id)
    load_start = time.perf_counter()

    # ---- Early-exit idempotency check ----
    # If a previous load_vector already finalised this doc, ANY subsequent
    # invocation (safety-net countdown, deferred retry, watchdog) should no-op.
    async def _check_already_finalized() -> tuple[bool, str | None, str | None]:
        session_factory = get_session_factory()
        async with session_factory() as session:
            doc_repo = DocumentRepository(session)
            log_repo = IngestionLogRepository(session)
            doc = await doc_repo.get(document_uuid)
            log = await log_repo.get_by_document(document_uuid)
            doc_status = doc.status if doc else None
            log_status = log.load_vector_status if log else None
            already = (doc_status == "success") or (log_status == "SUCCESS")
            return already, doc_status, log_status

    try:
        already_done, doc_status, log_status = run_async(_check_already_finalized())
    except Exception as exc:
        logger.warning(
            "kb_load_vector_preflight_check_failed", document_id=document_id, error=str(exc)
        )
        already_done = False
        doc_status = None
        log_status = None

    if already_done:
        logger.info(
            "kb_load_vector_skip_already_finalized",
            document_id=document_id,
            doc_status=doc_status,
            log_status=log_status,
            defer_attempt=defer_attempt,
            reissue_attempt=reissue_attempt,
            expected_total_batches=expected_total_batches,
            task_id=self.request.id if self.request else None,
        )
        return {"document_id": document_id, "skipped": True, "reason": "already_finalized"}

    # ---- Smart-defer gate (only the safety-net dispatch path) ----
    # If the safety-net countdown fires WHILE batches are still embedding, defer
    # via self.retry() rather than reissuing (which would duplicate upstream
    # calls). Bounded by _MAX_DEFER_ATTEMPTS; after that we assume some batches
    # died and fall through to verify+reissue (itself idempotent).
    if expected_total_batches > 0:
        progress = get_embed_progress(document_id)
        if progress < expected_total_batches:
            if defer_attempt < _MAX_DEFER_ATTEMPTS:
                logger.info(
                    "kb_load_vector_deferred_embed_in_progress",
                    document_id=document_id,
                    progress=progress,
                    expected_total_batches=expected_total_batches,
                    defer_attempt=defer_attempt,
                    max_defer_attempts=_MAX_DEFER_ATTEMPTS,
                    task_id=self.request.id if self.request else None,
                    retry_in_seconds=120,
                )
                raise self.retry(
                    kwargs={
                        "document_id": document_id,
                        "config_id": config_id,
                        "reissue_attempt": reissue_attempt,
                        "expected_total_batches": expected_total_batches,
                        "defer_attempt": defer_attempt + 1,
                    },
                    countdown=120,
                )
            logger.warning(
                "kb_load_vector_defer_budget_exhausted_forcing_reissue",
                document_id=document_id,
                progress=progress,
                expected_total_batches=expected_total_batches,
                defer_attempt=defer_attempt,
            )

    # Defensive S3 read — if staging is gone, this task is an orphan (doc
    # deleted mid-pipeline, or a delayed safety-net countdown fired after the
    # original last-batch dispatch already finalised + deleted staging).
    try:
        expected_count = _count_chunks_in_s3(document_id)
    except Exception as exc:
        if "NoSuchKey" in type(exc).__name__ or "NoSuchKey" in str(exc):
            logger.info(
                "kb_load_vector_skip_orphan_no_staging",
                document_id=document_id,
                task_id=self.request.id if self.request else None,
            )
            return {"document_id": document_id, "skipped": True, "reason": "orphan"}
        raise

    vector_repo = VectorRepository(worker_state.pg_engine)
    actual_count = vector_repo.count_document_embeddings(document_uuid)

    logger.info(
        "kb_load_vector_started",
        task_id=self.request.id if self.request else None,
        document_id=document_id,
        expected_count=expected_count,
        actual_count=actual_count,
        reissue_attempt=reissue_attempt,
    )

    async def _run() -> dict:
        session_factory = get_session_factory()
        async with session_factory() as session:
            doc_repo = DocumentRepository(session)
            log_repo = IngestionLogRepository(session)
            doc = await doc_repo.get(document_uuid)
            log = await log_repo.get_by_document(document_uuid) if doc else None

            # Idempotency: a previous load_vector may have finalised this doc.
            if log and log.load_vector_status == "SUCCESS":
                logger.info(
                    "kb_load_vector_skip_already_success",
                    document_id=document_id,
                    task_id=self.request.id if self.request else None,
                )
                return {
                    "document_id": document_id,
                    "embedding_count": actual_count,
                    "skipped": True,
                }

            if doc:
                await doc_repo.update_status(doc.id, "loading")
                await log_repo.update_stage(
                    doc.id,
                    stage="load_vector",
                    task_id=self.request.id if self.request else None,
                    status="STARTED",
                )
                _notify(document_id, "load_vector", "STARTED")

            if actual_count != expected_count:
                # Reissue path: re-dispatch only the missing chunks before failing.
                if reissue_attempt < _MAX_REISSUE_ATTEMPTS:
                    reissued = await asyncio.to_thread(
                        _reissue_missing_chunks, document_id, config_id
                    )
                    if reissued > 0:
                        logger.info(
                            "kb_load_vector_reissued",
                            document_id=document_id,
                            reissue_attempt=reissue_attempt,
                            chunks_reissued=reissued,
                            actual=actual_count,
                            expected=expected_count,
                        )
                        raise self.retry(
                            kwargs={
                                "document_id": document_id,
                                "config_id": config_id,
                                "reissue_attempt": reissue_attempt + 1,
                            },
                            countdown=_REISSUE_WAIT_SECONDS,
                            max_retries=_MAX_REISSUE_ATTEMPTS + 3,
                        )
                    # No missing chunks but count still wrong? Race — short retry.
                    if self.request and self.request.retries < 2:
                        raise self.retry(
                            exc=ValueError(
                                "vec count mismatch with no missing indices — retrying"
                            ),
                            countdown=30,
                        )

                error = (
                    f"Vector count mismatch for document {document_id}: "
                    f"{actual_count} vectors in DB vs {expected_count} chunks staged. "
                    f"Exhausted {_MAX_REISSUE_ATTEMPTS} reissue passes."
                )
                if doc:
                    await doc_repo.update_status(doc.id, "failed")
                    await log_repo.update_stage(
                        doc.id, stage="load_vector", status="FAILURE", error_message=error
                    )
                    _notify(document_id, "load_vector", "FAILURE", error)
                    _notify(document_id, "pipeline", "failed", error)
                raise ValueError(error)

            # All batches accounted for — mark embed + load_vector SUCCESS.
            if doc:
                await log_repo.update_stage(doc.id, stage="embed", status="SUCCESS")
                _notify(document_id, "embed", "SUCCESS")
                await doc_repo.update_status(doc.id, "success")
                await log_repo.update_stage(doc.id, stage="load_vector", status="SUCCESS")
                _notify(document_id, "load_vector", "SUCCESS")
                _notify(document_id, "pipeline", "success")

            # Clean up staging — chunks now live permanently in pgvector.
            await asyncio.to_thread(_delete_staging_file, document_id)
            reset_embed_progress(document_id)

            elapsed_ms = int((time.perf_counter() - load_start) * 1000)
            logger.info(
                "kb_load_vector_completed",
                task_id=self.request.id if self.request else None,
                document_id=document_id,
                vector_count=actual_count,
                elapsed_ms=elapsed_ms,
            )
            return {"document_id": document_id, "embedding_count": actual_count}

    return run_async(_run())


# ---------------------------------------------------------------------------
