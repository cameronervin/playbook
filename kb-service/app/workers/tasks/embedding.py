"""Embedding fan-out and per-batch Celery tasks for the KB pipeline."""
from __future__ import annotations

import asyncio
import random
import time
import uuid
from collections.abc import Iterator

import structlog
from celery import group
from celery.exceptions import MaxRetriesExceededError

from app.workers.app import kb_worker
from app.workers.tasks.notify import _notify
from app.workers.tasks.progress import increment_embed_progress, reset_embed_progress
from app.workers.tasks.staging import _load_chunk_slice_from_s3

logger = structlog.get_logger(__name__)

# ---------------------------------------------------------------------------
# Batch planning helpers.
# ---------------------------------------------------------------------------
def _plan_batches(total_chunks: int, batch_size: int) -> list[tuple[int, int]]:
    """Return a list of (chunk_start, chunk_end) half-open index windows.

    Splits ``range(total_chunks)`` into windows of at most ``batch_size`` so each
    embed_batch_task knows exactly which slice of the staged NDJSON to read.
    """
    if batch_size <= 0:
        raise ValueError("batch_size must be greater than 0")
    windows: list[tuple[int, int]] = []
    start = 0
    while start < total_chunks:
        end = min(start + batch_size, total_chunks)
        windows.append((start, end))
        start = end
    return windows


def _batch_chunks(
    chunks: list[dict],
    *,
    batch_size: int = 64,
    max_batch_chars: int = 60_000,
) -> Iterator[list[dict]]:
    """Yield resource-bounded chunk batches (count + approx char volume).

    Retained for the reissue-recovery path which works on already-loaded chunk
    slices. The primary embed fan-out uses ``_plan_batches`` index windows.
    """
    if batch_size <= 0:
        raise ValueError("batch_size must be greater than 0")
    if max_batch_chars <= 0:
        raise ValueError("max_batch_chars must be greater than 0")

    current_batch: list[dict] = []
    current_chars = 0
    for chunk in chunks:
        chunk_text = chunk.get("text", "") if isinstance(chunk, dict) else ""
        chunk_chars = len(chunk_text) if isinstance(chunk_text, str) else 0
        would_exceed_count = len(current_batch) >= batch_size
        would_exceed_chars = current_batch and (current_chars + chunk_chars > max_batch_chars)
        if would_exceed_count or would_exceed_chars:
            yield current_batch
            current_batch = []
            current_chars = 0
        current_batch.append(chunk)
        current_chars += chunk_chars

    if current_batch:
        yield current_batch


def _extract_texts(chunks: list[dict]) -> list[str]:
    """Return the non-empty ``text`` fields from chunk dicts, validating shape."""
    texts: list[str] = []
    for chunk in chunks:
        if not isinstance(chunk, dict):
            raise TypeError("Each chunk must include a string text field")
        text_value = chunk.get("text")
        if not isinstance(text_value, str):
            raise TypeError("Each chunk must include a string text field")
        if text_value.strip():
            texts.append(text_value)
    return texts


def _compute_retry_countdown(
    retry_number: int,
    *,
    retry_after_seconds: float | None = None,
) -> int:
    """Exponential backoff (with optional jitter), honouring a server retry-after hint."""
    from app.core.config import settings

    if retry_after_seconds is not None:
        return max(1, int(retry_after_seconds))

    base = max(settings.KB_EMBED_BACKOFF_BASE_SECONDS, 1)
    cap = max(settings.KB_EMBED_BACKOFF_MAX_SECONDS, base)
    delay = min(base * (2 ** max(retry_number - 1, 0)), cap)
    if settings.KB_EMBED_RETRY_JITTER:
        delay = delay + random.randint(0, base)
    return int(delay)


# ---------------------------------------------------------------------------
# embed_task — fan-out dispatcher (chain step; receives chunk_task's prev dict).
# ---------------------------------------------------------------------------
@kb_worker.task(bind=True, name="app.workers.tasks.embed_task", max_retries=2)
def embed_task(self, prev: dict, *, document_id: str, config_id: str) -> dict:
    """Fan out embedding batches as a plain group (no chord).

    Each batch reads its own chunk slice from S3, writes its vectors directly to
    pgvector, and increments a Redis counter; the last-completing batch
    dispatches load_vector_task. See module docstring for why we abandoned chord.

    Pre-flight wipes any stale vectors for this document so a re-ingest is clean.
    """
    from app.core.config import settings
    from app.infrastructure.parsers.contracts.errors import NoTextExtractedError
    from app.repositories.vector_repo import VectorRepository
    from app.workers.state import worker_state

    chunk_count = prev.get("chunk_count", 0) if isinstance(prev, dict) else 0
    if chunk_count <= 0:
        no_text_error = NoTextExtractedError(stage="embed")
        logger.info(
            "kb_no_text_extracted",
            document_id=document_id,
            stage="embed",
            chunk_count=chunk_count,
            error_code=no_text_error.code,
        )
        _notify(document_id, "embed", "FAILURE", str(no_text_error))
        _notify(document_id, "pipeline", "failed", str(no_text_error))
        raise no_text_error

    document_uuid = uuid.UUID(document_id)

    # Clear any stale vectors from a previous run, and reset the progress counter.
    vector_repo = VectorRepository(worker_state.pg_engine)
    vector_repo.delete_document_embeddings(document_uuid)
    reset_embed_progress(document_id)

    # Cap the number of concurrent batches by widening batch_size if needed.
    min_batch_size_for_cap = max(
        settings.KB_EMBED_BATCH_SIZE,
        (chunk_count + settings.KB_EMBED_MAX_CONCURRENT_BATCHES - 1)
        // settings.KB_EMBED_MAX_CONCURRENT_BATCHES,
    )
    windows = _plan_batches(chunk_count, min_batch_size_for_cap)
    total_batches = len(windows)

    batch_signatures = [
        embed_batch_task.s(
            document_id=document_id,
            config_id=config_id,
            batch_index=batch_index,
            chunk_start=chunk_start,
            chunk_end=chunk_end,
            total_batches=total_batches,
        )
        for batch_index, (chunk_start, chunk_end) in enumerate(windows)
    ]

    # Plain group — no chord. Last batch in embed_batch_task dispatches load_vector.
    # Queue routing flows from task_routes config (kb-io for embed_batch_task).
    group(batch_signatures).apply_async()

    # Safety-net dispatch: schedule a load_vector_task to fire AFTER the group
    # has had time to complete. If all batches succeed normally the last-batch
    # dispatch fires load_vector first and this fallback is a no-op (load_vector
    # is idempotent). expected_total_batches lets load_vector verify the embed
    # phase is genuinely complete before touching the reissue path.
    fallback_delay = max(180, min(3600, total_batches * 8 + 180))
    from app.workers.tasks.finalize import load_vector_task

    load_vector_task.apply_async(
        kwargs={
            "document_id": document_id,
            "config_id": config_id,
            "expected_total_batches": total_batches,
        },
        countdown=fallback_delay,
    )

    logger.info(
        "kb_embed_task_dispatched",
        document_id=document_id,
        total_batches=total_batches,
        total_chunks=chunk_count,
        fallback_load_vector_in=fallback_delay,
    )
    return {"batch_count": total_batches}


# ---------------------------------------------------------------------------
# embed_batch_task — embeds one chunk slice; runs on the kb-io threads pool.
# ---------------------------------------------------------------------------
@kb_worker.task(
    bind=True,
    name="app.workers.tasks.embed_batch_task",
    max_retries=5,
    rate_limit="45/m",  # Hard ceiling; the distributed limiter is the real throttle.
)
def embed_batch_task(
    self,
    *,
    document_id: str,
    config_id: str,
    batch_index: int,
    chunk_start: int,
    chunk_end: int,
    total_batches: int = 0,
) -> dict:
    """Embed a single chunk slice (read from S3) and write it straight into pgvector.

    Each batch is fully self-contained:
      1. Read its chunk window [chunk_start, chunk_end) from the staged NDJSON.
      2. Embed those chunks via LiteLLM (guarded by the distributed limiter,
         retry on 429/5xx with exp backoff honouring retry-after).
      3. INSERT this batch's vectors directly into kb.langchain_pg_embedding
         (idempotent — the batch's own chunk_index range is wiped before insert
         so retries don't double-write).
      4. Atomically increment the per-document progress counter in Redis.
      5. If we are the LAST batch (counter == total_batches), dispatch
         load_vector_task to finalize. ``total_batches == 0`` is the reissue
         sentinel — such batches never auto-dispatch load_vector.

    Returns a small summary dict — no embeddings travel through the broker.
    """
    from app.core.config import settings
    from app.infrastructure.db.session import get_session_factory
    from app.infrastructure.embedders.base import (
        EmbedRateLimitError,
        EmbedTransientError,
        normalize_embed_exception,
    )
    from app.repositories.document_repo import DocumentRepository
    from app.repositories.ingestion_log_repo import IngestionLogRepository
    from app.repositories.vector_repo import VectorRepository
    from app.workers.app import run_async
    from app.workers.rate_limiter import acquire_embed_slot, release_embed_slot
    from app.workers.state import worker_state

    document_uuid = uuid.UUID(document_id)
    config_uuid = uuid.UUID(config_id)
    chunks = _load_chunk_slice_from_s3(document_id, chunk_start, chunk_end)
    texts = _extract_texts(chunks)
    embed_start = time.perf_counter()

    logger.info(
        "kb_embed_batch_started",
        task_id=self.request.id if self.request else None,
        document_id=document_id,
        batch_index=batch_index,
        batch_size=len(chunks),
        chunk_start=chunk_start,
        chunk_end=chunk_end,
        total_batches=total_batches,
    )

    async def _run() -> dict:
        if worker_state.embed_client is None:
            raise RuntimeError("worker_state.embed_client is not initialized")

        session_factory = get_session_factory()
        async with session_factory() as session:
            doc_repo = DocumentRepository(session)
            log_repo = IngestionLogRepository(session)
            doc = await doc_repo.get(document_uuid)
            if doc is None:
                vector_repo = VectorRepository(worker_state.pg_engine)
                await asyncio.to_thread(
                    vector_repo.delete_document_embeddings,
                    document_uuid,
                )
                reset_embed_progress(document_id)
                logger.info(
                    "kb_embed_batch_skip_deleted_document",
                    task_id=self.request.id if self.request else None,
                    document_id=document_id,
                    batch_index=batch_index,
                    reason="document_missing_before_embed",
                )
                return {
                    "document_id": document_id,
                    "batch_index": batch_index,
                    "batch_size": len(chunks),
                    "status": "skipped_deleted_document",
                }
            if doc:
                # First-batch wins: flips doc to 'embedding' and stage to STARTED.
                await doc_repo.update_status(doc.id, "embedding")
                await log_repo.update_stage(
                    doc.id,
                    stage="embed",
                    task_id=self.request.id if self.request else None,
                    status="STARTED",
                )
                _notify(document_id, "embed", "STARTED")

            # Distributed throttle: blocks until the embedding upstream RPM and
            # concurrent gates both have a slot. Prevents the burst-storm that
            # occurs when group().apply_async() fans out many batches.
            await asyncio.to_thread(acquire_embed_slot)
            try:
                try:
                    # Sync client — must run off the event loop or it would block
                    # the async session. to_thread offloads the blocking HTTP call.
                    embeddings = await asyncio.to_thread(worker_state.embed_client.embed, texts)
                except Exception as exc:
                    normalized = normalize_embed_exception(exc)
                    if isinstance(normalized, (EmbedRateLimitError, EmbedTransientError)):
                        retry_after = (
                            normalized.retry_after_seconds
                            if isinstance(normalized, EmbedRateLimitError)
                            else None
                        )
                        countdown = _compute_retry_countdown(
                            self.request.retries + 1 if self.request else 1,
                            retry_after_seconds=retry_after,
                        )
                        logger.warning(
                            "kb_embed_batch_retry_scheduled",
                            task_id=self.request.id if self.request else None,
                            document_id=document_id,
                            batch_index=batch_index,
                            batch_size=len(chunks),
                            error_class=type(normalized).__name__,
                            error_message=str(normalized),
                            retry_attempt=(self.request.retries + 1) if self.request else 1,
                            retry_in_seconds=countdown,
                            retry_after_hint=retry_after,
                            max_retries=settings.KB_EMBED_MAX_RETRIES,
                        )
                        try:
                            # Normal path: raises Retry (caught by Celery).
                            # Final path: raises MaxRetriesExceededError (caught here).
                            self.retry(
                                exc=normalized,
                                countdown=countdown,
                                max_retries=settings.KB_EMBED_MAX_RETRIES,
                            )
                        except MaxRetriesExceededError:
                            logger.error(
                                "kb_embed_batch_failed_permanent",
                                task_id=self.request.id if self.request else None,
                                document_id=document_id,
                                batch_index=batch_index,
                                batch_size=len(chunks),
                                retries_attempted=settings.KB_EMBED_MAX_RETRIES,
                                error_message=str(normalized),
                            )
                            if doc:
                                await doc_repo.update_status(doc.id, "failed")
                                await log_repo.update_stage(
                                    doc.id,
                                    stage="embed",
                                    status="FAILURE",
                                    error_message=str(normalized),
                                )
                                _notify(document_id, "embed", "FAILURE", str(normalized))
                                _notify(document_id, "pipeline", "failed", str(normalized))
                            # Return cleanly so Celery does not dump a traceback —
                            # the failure is fully captured; the doc is marked
                            # failed in the DB (the source of truth).
                            return {
                                "document_id": document_id,
                                "batch_index": batch_index,
                                "batch_size": len(chunks),
                                "status": "failed_max_retries",
                            }
                    # Permanent (non-retriable) failure — same clean treatment.
                    logger.error(
                        "kb_embed_batch_failed_permanent",
                        task_id=self.request.id if self.request else None,
                        document_id=document_id,
                        batch_index=batch_index,
                        batch_size=len(chunks),
                        retries_attempted=(self.request.retries if self.request else 0),
                        reason="non_retriable_error",
                        error_message=str(normalized),
                    )
                    if doc:
                        await doc_repo.update_status(doc.id, "failed")
                        await log_repo.update_stage(
                            doc.id,
                            stage="embed",
                            status="FAILURE",
                            error_message=str(normalized),
                        )
                        _notify(document_id, "embed", "FAILURE", str(normalized))
                        _notify(document_id, "pipeline", "failed", str(normalized))
                    return {
                        "document_id": document_id,
                        "batch_index": batch_index,
                        "batch_size": len(chunks),
                        "status": "failed_non_retriable",
                    }
            finally:
                # Always release the in-flight slot, even on retry/raise, so the
                # concurrent budget does not leak between batches.
                await asyncio.to_thread(release_embed_slot)

            if len(embeddings) != len(texts):
                raise ValueError(
                    f"Embedding output count mismatch: {len(embeddings)} != {len(texts)}"
                )

            latest_doc = await doc_repo.get(document_uuid)
            # Write this batch's vectors to pgvector. Idempotent on retry — the
            # global chunk_index range [chunk_start, chunk_end) is cleared first.
            vector_repo = VectorRepository(worker_state.pg_engine)
            if latest_doc is None:
                await asyncio.to_thread(
                    vector_repo.delete_document_embeddings,
                    document_uuid,
                )
                reset_embed_progress(document_id)
                logger.info(
                    "kb_embed_batch_skip_deleted_document",
                    task_id=self.request.id if self.request else None,
                    document_id=document_id,
                    batch_index=batch_index,
                    reason="document_missing_before_vector_insert",
                )
                return {
                    "document_id": document_id,
                    "batch_index": batch_index,
                    "batch_size": len(chunks),
                    "status": "skipped_deleted_document",
                }
            await asyncio.to_thread(
                vector_repo.insert_batch_embeddings,
                configuration_id=config_uuid,
                document_id=document_uuid,
                chunks=chunks,
                embeddings=embeddings,
                chunk_index_offset=chunk_start,
            )

            elapsed_ms = int((time.perf_counter() - embed_start) * 1000)
            logger.info(
                "kb_embed_batch_completed",
                task_id=self.request.id if self.request else None,
                document_id=document_id,
                batch_index=batch_index,
                embedding_count=len(embeddings),
                chunk_start=chunk_start,
                elapsed_ms=elapsed_ms,
            )

        # Outside the session — counter + dispatch must not hold a DB connection.
        completed = increment_embed_progress(document_id)
        logger.info(
            "kb_embed_progress",
            document_id=document_id,
            completed=completed,
            total=total_batches,
        )
        if completed >= total_batches and total_batches > 0:
            # Last-batch dispatcher — race-safe because INCR is atomic. Only one
            # batch sees ``completed == total``. Higher values mean a retry pushed
            # past total — load_vector_task is idempotent so duplicate fires are fine.
            from app.workers.tasks.finalize import load_vector_task

            load_vector_task.apply_async(
                kwargs={"document_id": document_id, "config_id": config_id},
            )
            logger.info(
                "kb_embed_finalize_dispatched",
                document_id=document_id,
                completed=completed,
                total=total_batches,
            )

        return {
            "document_id": document_id,
            "batch_index": batch_index,
            "batch_size": len(embeddings),
            "completed": completed,
            "total": total_batches,
        }

    return run_async(_run())


# ---------------------------------------------------------------------------
