"""S3 NDJSON staging helpers for KB worker tasks."""
from __future__ import annotations

import structlog

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


def _load_chunk_indices_from_s3(document_id: str, indices: list[int]) -> list[dict]:
    """Return selected chunk indices from S3 staging without loading all chunks."""
    import json

    from app.core.config import settings
    from app.infrastructure.io.s3_client import build_s3_client

    wanted = set(indices)
    if not wanted:
        return []

    response = build_s3_client().get_object(
        Bucket=settings.S3_BUCKET_NAME, Key=_staging_key(document_id)
    )
    body = response["Body"]
    out: list[dict] = []
    index = 0
    max_index = max(wanted)
    try:
        for raw_line in body.iter_lines():
            if not raw_line:
                continue
            if index in wanted:
                out.append(json.loads(raw_line))
            if index >= max_index:
                break
            index += 1
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
