"""KB pipeline Celery tasks.

Chain: parse_task → chunk_task → embed_task → group(embed_batch_task) → load_vector_task
       notify_status_task is dispatched at every stage transition.

embed → load_vector is **not** wired via a Celery chord — chord_unlock proved
unreliable at high fanout (50+ batches). Instead each embed_batch_task writes
its slice of vectors directly to pgvector and atomically increments a Redis
counter; the last-completing batch dispatches load_vector_task as a plain
follow-up (finalization only — no embedding payload travels through the broker).

Heavy / network-touching imports (boto3, httpx, redis) are done lazily inside
the functions; ``celery`` internals are needed at module load for the task
decorators (the test suite shims ``celery`` so this stays importable with no
broker). The chunk slices, page text, and embeddings are staged in S3 as NDJSON
so the broker only ever carries small summary dicts.
"""
from __future__ import annotations

import asyncio
import random
import time
import uuid
from collections.abc import Iterator

import structlog
from celery import group
from celery.exceptions import MaxRetriesExceededError, SoftTimeLimitExceeded

from app.workers.app import kb_worker

logger = structlog.get_logger(__name__)

# ---------------------------------------------------------------------------
# S3 NDJSON staging — keeps page text and chunks off the Redis broker.
# parse_task stages page text; chunk_task stages chunks; embed_batch_task and
# load_vector_task read them back. Staging is deleted after a successful
# load_vector pass.
# ---------------------------------------------------------------------------
_STAGING_PREFIX = "kb/staging"


def _staging_key(document_id: str) -> str:
    # NDJSON: one chunk per line — streamable on both write and read.
    return f"{_STAGING_PREFIX}/{document_id}/chunks.ndjson"


def _pages_staging_key(document_id: str) -> str:
    # NDJSON: one page per line — streamable.
    return f"{_STAGING_PREFIX}/{document_id}/pages.ndjson"


def _save_pages_to_s3(document_id: str, pages) -> str:
    """Stage parser output to S3 as NDJSON so it doesn't flow through the broker.

    parse_task → chunk_task used to pass the full pages list (can be MBs) as
    the Celery task result, which serialised through Redis. Now the pages live
    in S3 and the result is a small dict.
    """
    import json
    from tempfile import SpooledTemporaryFile

    from app.core.config import settings
    from app.infrastructure.io.s3_client import build_s3_client

    key = _pages_staging_key(document_id)
    spool_max = settings.S3_STREAM_SPOOL_MAX_SIZE_MB * 1024 * 1024
    count = 0
    with SpooledTemporaryFile(max_size=spool_max, mode="w+b") as buf:
        for page in pages:
            line = json.dumps(page, ensure_ascii=False) + "\n"
            buf.write(line.encode("utf-8"))
            count += 1
        buf.seek(0)
        build_s3_client().upload_fileobj(
            buf,
            Bucket=settings.S3_BUCKET_NAME,
            Key=key,
            ExtraArgs={"ContentType": "application/x-ndjson"},
        )
    logger.info("kb_pages_staged", document_id=document_id, page_count=count, key=key)
    return key


def _iter_pages_from_s3(document_id: str):
    """Yield pages one at a time from the staging NDJSON file in S3.

    Keeps chunk_task's memory peak bounded by ONE page at a time instead of
    the full pages list.
    """
    import json

    from app.core.config import settings
    from app.infrastructure.io.s3_client import build_s3_client

    response = build_s3_client().get_object(
        Bucket=settings.S3_BUCKET_NAME, Key=_pages_staging_key(document_id)
    )
    body = response["Body"]
    try:
        for raw_line in body.iter_lines():
            if not raw_line:
                continue
            yield json.loads(raw_line)
    finally:
        body.close()


def _delete_pages_staging(document_id: str) -> None:
    from app.core.config import settings
    from app.infrastructure.io.s3_client import build_s3_client

    try:
        build_s3_client().delete_object(
            Bucket=settings.S3_BUCKET_NAME, Key=_pages_staging_key(document_id)
        )
    except Exception as exc:
        logger.warning("kb_pages_delete_failed", document_id=document_id, error=str(exc))


def _save_chunks_to_s3(document_id: str, chunks) -> str:
    """Stream chunks to S3 as NDJSON via a SpooledTemporaryFile.

    Accepts a list or any iterable of dicts. Writes one JSON object per line
    into a spooled buffer (RAM until SPOOL_MAX_SIZE_MB, then disk) and uploads
    via boto3's upload_fileobj. Avoids materialising both the chunks list AND
    a serialised JSON blob in memory at the same time.
    """
    import json
    from tempfile import SpooledTemporaryFile

    from app.core.config import settings
    from app.infrastructure.io.s3_client import build_s3_client

    key = _staging_key(document_id)
    spool_max = settings.S3_STREAM_SPOOL_MAX_SIZE_MB * 1024 * 1024

    with SpooledTemporaryFile(max_size=spool_max, mode="w+b") as buf:
        count = 0
        for chunk in chunks:
            line = json.dumps(chunk, separators=(",", ":"), ensure_ascii=False) + "\n"
            buf.write(line.encode("utf-8"))
            count += 1
        buf.seek(0)
        build_s3_client().upload_fileobj(
            buf,
            Bucket=settings.S3_BUCKET_NAME,
            Key=key,
            ExtraArgs={"ContentType": "application/x-ndjson"},
        )
    logger.info("kb_chunks_staged", document_id=document_id, chunk_count=count, key=key)
    return key


def _load_chunks_from_s3(document_id: str) -> list[dict]:
    """Stream NDJSON back from S3 and parse line-by-line into a list[dict]."""
    import json

    from app.core.config import settings
    from app.infrastructure.io.s3_client import build_s3_client

    response = build_s3_client().get_object(
        Bucket=settings.S3_BUCKET_NAME, Key=_staging_key(document_id)
    )
    chunks: list[dict] = []
    body = response["Body"]
    try:
        for raw_line in body.iter_lines():
            if not raw_line:
                continue
            chunks.append(json.loads(raw_line))
    finally:
        body.close()
    return chunks


def _load_chunk_slice_from_s3(document_id: str, chunk_start: int, chunk_end: int) -> list[dict]:
    """Return chunks in the half-open range [chunk_start, chunk_end) from S3 staging.

    embed_batch_task receives only its index window (not the chunks inline) so
    the broker stays small even for very large documents. We stream the NDJSON
    and keep only the lines that fall inside this batch's window.
    """
    import json

    from app.core.config import settings
    from app.infrastructure.io.s3_client import build_s3_client

    response = build_s3_client().get_object(
        Bucket=settings.S3_BUCKET_NAME, Key=_staging_key(document_id)
    )
    body = response["Body"]
    out: list[dict] = []
    index = 0
    try:
        for raw_line in body.iter_lines():
            if not raw_line:
                continue
            if chunk_start <= index < chunk_end:
                out.append(json.loads(raw_line))
            index += 1
            if index >= chunk_end:
                break
    finally:
        body.close()
    return out


def _count_chunks_in_s3(document_id: str) -> int:
    """Count NDJSON lines in the chunk staging file without parsing each line."""
    from app.core.config import settings
    from app.infrastructure.io.s3_client import build_s3_client

    response = build_s3_client().get_object(
        Bucket=settings.S3_BUCKET_NAME, Key=_staging_key(document_id)
    )
    body = response["Body"]
    count = 0
    try:
        for raw_line in body.iter_lines():
            if raw_line:
                count += 1
    finally:
        body.close()
    return count


def _delete_staging_file(document_id: str) -> None:
    from app.core.config import settings
    from app.infrastructure.io.s3_client import build_s3_client

    try:
        build_s3_client().delete_object(
            Bucket=settings.S3_BUCKET_NAME, Key=_staging_key(document_id)
        )
    except Exception as exc:
        logger.warning("kb_staging_delete_failed", document_id=document_id, error=str(exc))


def _notify(
    document_id: str,
    stage: str,
    status: str,
    error_message: str | None = None,
) -> None:
    """Fire-and-forget notify dispatch — broker failure must not crash the pipeline task."""
    try:
        notify_status_task.delay(
            document_id=document_id,
            stage=stage,
            status=status,
            error_message=error_message,
        )
    except Exception:
        logger.warning(
            "kb_notify_dispatch_failed",
            document_id=document_id,
            stage=stage,
            status=status,
        )


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
    from app.infrastructure.parsers.contracts.errors import CorruptFileError, OCRTimeoutError
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
                    suffix=f".{filename.split('.')[-1].lower()}" if "." in filename else "",
                ) as tmp_path:
                    outcome = await router.route_path(
                        path=tmp_path,
                        filename=filename,
                        s3_bucket=settings.S3_BUCKET_NAME,
                        s3_key=s3_key,
                    )
            except (OCRTimeoutError, TimeoutError, SoftTimeLimitExceeded) as exc:
                if doc:
                    await log_repo.update_stage(
                        doc.id, stage="parse", status="FAILURE", error_message=str(exc)
                    )
                    _notify(document_id, "parse", "FAILURE", str(exc))
                raise self.retry(exc=exc)
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
    from app.infrastructure.db.session import get_session_factory
    from app.infrastructure.chunkers.token_based import iter_chunks_from_pages
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
                raise self.retry(exc=exc)
            except Exception as exc:
                if doc:
                    await doc_repo.update_status(doc.id, "failed")
                    await log_repo.update_stage(
                        doc.id, stage="chunk", status="FAILURE", error_message=str(exc)
                    )
                    _notify(document_id, "chunk", "FAILURE", str(exc))
                raise

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
# Embed progress counter — replaces Celery's chord_unlock for tracking completion.
# Stored in the Celery result-backend Redis so it shares the connection pool.
# ---------------------------------------------------------------------------
_EMBED_PROGRESS_TTL_SECONDS = 86400  # 24h — far longer than any real pipeline


def _embed_progress_key(document_id: str) -> str:
    return f"kb:embed_progress:{document_id}"


def _get_result_backend_client():
    """Return the raw redis client used by the result backend (lazy — no import-time conn)."""
    from celery import current_app

    return current_app.backend.client


def reset_embed_progress(document_id: str) -> None:
    """Clear the per-document batch completion counter. Called at embed_task start."""
    try:
        _get_result_backend_client().delete(_embed_progress_key(document_id))
    except Exception as exc:
        logger.warning("kb_embed_progress_reset_failed", document_id=document_id, error=str(exc))


def get_embed_progress(document_id: str) -> int:
    """Read the per-document batch completion counter without incrementing it.

    Used by load_vector_task's smart-defer check: if ``progress < total`` the
    embed phase is still in flight and we must NOT reissue. Returns 0 if the key
    does not exist or Redis is unreachable.
    """
    try:
        client = _get_result_backend_client()
        value = client.get(_embed_progress_key(document_id))
        if value is None:
            return 0
        return int(value)
    except Exception as exc:
        logger.warning("kb_embed_progress_get_failed", document_id=document_id, error=str(exc))
        return 0


def increment_embed_progress(document_id: str) -> int:
    """Atomically increment the counter and return the new value.

    Returns 0 on Redis failure so the last-batch dispatch path is skipped — the
    safety-net (load_vector self-check) will still close the loop.
    """
    try:
        client = _get_result_backend_client()
        key = _embed_progress_key(document_id)
        new_value = client.incr(key)
        client.expire(key, _EMBED_PROGRESS_TTL_SECONDS)
        return int(new_value)
    except Exception as exc:
        logger.warning("kb_embed_progress_incr_failed", document_id=document_id, error=str(exc))
        return 0


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
    from app.repositories.vector_repo import VectorRepository
    from app.workers.state import worker_state

    chunk_count = prev.get("chunk_count", 0) if isinstance(prev, dict) else 0
    if chunk_count <= 0:
        return {"batch_count": 0}

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

            # Write this batch's vectors to pgvector. Idempotent on retry — the
            # global chunk_index range [chunk_start, chunk_end) is cleared first.
            vector_repo = VectorRepository(worker_state.pg_engine)
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
# notify_status_task — outbound HMAC-signed status webhook to the calling app.
# ---------------------------------------------------------------------------
@kb_worker.task(
    bind=True,
    name="app.workers.tasks.notify_status_task",
    max_retries=5,
    default_retry_delay=2,
)
def notify_status_task(
    self,
    *,
    document_id: str,
    status: str,
    stage: str | None = None,
    error_message: str | None = None,
) -> None:
    """HMAC-SHA256 sign and POST a status update to the calling app's webhook.

    Posts to ``{settings.APP_WEBHOOK_URL}/api/v1/kb/webhook`` with an
    ``X-KB-Signature: sha256=<hex>`` header. On permanent failure (all retries
    exhausted), the delivery is dead-lettered into kb.ingestion_logs so the
    caller's reconciler can recover terminal events on its next run.
    """
    import hashlib
    import hmac
    import json
    import time as _time

    import httpx

    from app.core.config import settings

    payload = {
        "document_id": document_id,
        "stage": stage,
        "status": status,
        "error_message": error_message,
        "timestamp": int(_time.time()),
    }
    body = json.dumps(payload, separators=(",", ":")).encode()
    signature = hmac.new(
        settings.KB_WEBHOOK_SECRET.encode(),
        body,
        hashlib.sha256,
    ).hexdigest()

    url = f"{settings.APP_WEBHOOK_URL.rstrip('/')}/api/v1/kb/webhook"
    headers = {
        "Content-Type": "application/json",
        "X-KB-Signature": f"sha256={signature}",
    }
    try:
        response = httpx.post(url, content=body, headers=headers, timeout=10)
        response.raise_for_status()
        logger.info(
            "kb_webhook_sent",
            document_id=document_id,
            stage=stage,
            status=status,
            http_status=response.status_code,
        )
    except httpx.HTTPStatusError as exc:
        logger.warning(
            "kb_webhook_http_error",
            document_id=document_id,
            stage=stage,
            status=status,
            http_status=exc.response.status_code,
        )
        if self.request.retries >= self.max_retries:
            _handle_webhook_dead_letter(self.request.id, document_id, stage, status, exc)
        raise self.retry(exc=exc)
    except httpx.TransportError as exc:
        logger.warning(
            "kb_webhook_transport_error",
            document_id=document_id,
            stage=stage,
            status=status,
            error=str(exc),
        )
        if self.request.retries >= self.max_retries:
            _handle_webhook_dead_letter(self.request.id, document_id, stage, status, exc)
        raise self.retry(exc=exc)


def _handle_webhook_dead_letter(
    task_id: str | None,
    document_id: str | None,
    stage: str | None,
    status: str | None,
    exc: Exception,
) -> None:
    """Log dead-letter at ERROR and persist to kb.ingestion_logs.

    Called when notify_status_task exhausts all retries. The ERROR log is the
    breadcrumb hook point for future alerting.
    """
    logger.error(
        "kb_webhook_dead_lettered",
        task_id=task_id,
        document_id=document_id,
        stage=stage,
        status=status,
        error=str(exc),
        exc_info=True,
    )

    if not document_id:
        return

    from app.infrastructure.db.session import get_session_factory
    from app.workers.app import run_async

    async def _persist() -> None:
        session_factory = get_session_factory()
        async with session_factory() as session:
            from app.repositories.ingestion_log_repo import IngestionLogRepository

            try:
                doc_uuid = uuid.UUID(document_id)
            except ValueError:
                return
            log_repo = IngestionLogRepository(session)
            await log_repo.update_stage(
                doc_uuid,
                stage=stage or "notify",
                status="DEAD_LETTERED",
                error_message=f"webhook delivery exhausted retries: {exc}",
            )

    try:
        run_async(_persist())
    except Exception as persist_exc:
        logger.warning(
            "kb_webhook_dead_letter_persist_failed",
            document_id=document_id,
            error=str(persist_exc),
        )


# ---------------------------------------------------------------------------
# Watchdog — covers corner cases where the last-batch-dispatch in
# embed_batch_task never runs (worker crash before INCR, Redis INCR failure,
# unanticipated MaxRetriesExceededError path). For any document whose embed has
# been STARTED but never finalized for > N minutes, dispatch load_vector_task.
# ---------------------------------------------------------------------------
_STUCK_EMBED_MINUTES_DEFAULT = 5


@kb_worker.task(bind=True, name="app.workers.tasks.reconcile_stuck_embeds", max_retries=0)
def reconcile_stuck_embeds(self, stuck_minutes: int = _STUCK_EMBED_MINUTES_DEFAULT) -> dict:
    """Find docs stuck mid-embed and re-dispatch load_vector_task for them.

    Returns a summary {scanned, dispatched, doc_ids, stuck_minutes}.

    Stuck definition:
      embed_status = 'STARTED'        (embed phase began)
      AND load_vector_status IS NULL  (never finalized)
      AND updated_at < NOW() - stuck_minutes
    """
    from sqlalchemy import text

    from app.infrastructure.db.session import get_session_factory
    from app.workers.app import run_async

    async def _run() -> dict:
        session_factory = get_session_factory()
        async with session_factory() as session:
            result = await session.execute(
                text(
                    """
                    SELECT l.document_id, d.configuration_id
                    FROM kb.ingestion_logs l
                    JOIN kb.documents d ON d.id = l.document_id
                    WHERE l.embed_status = 'STARTED'
                      AND l.load_vector_status IS NULL
                      AND l.updated_at < (NOW() AT TIME ZONE 'UTC') - (:mins * INTERVAL '1 minute')
                    ORDER BY l.updated_at ASC
                    LIMIT 50
                    """
                ),
                {"mins": stuck_minutes},
            )
            rows = result.fetchall()

        dispatched: list[str] = []
        for row in rows:
            document_id = str(row[0])
            config_id = str(row[1])
            try:
                load_vector_task.apply_async(
                    kwargs={"document_id": document_id, "config_id": config_id},
                )
                dispatched.append(document_id)
                logger.info(
                    "kb_watchdog_dispatched_load_vector",
                    document_id=document_id,
                    config_id=config_id,
                )
            except Exception as exc:
                logger.warning(
                    "kb_watchdog_dispatch_failed", document_id=document_id, error=str(exc)
                )

        summary = {
            "scanned": len(rows),
            "dispatched": len(dispatched),
            "doc_ids": dispatched,
            "stuck_minutes": stuck_minutes,
        }
        logger.info("kb_watchdog_completed", **summary)
        return summary

    return run_async(_run())
