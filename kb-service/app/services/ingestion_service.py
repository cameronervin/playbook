"""Ingestion service — validates, records, and dispatches the document pipeline.

Flow of start_ingest:
  1. Resolve the configuration.
  2. HEAD the S3 object to enforce the max-size guard (cheap) before the MD5
     download (streams the full object).
  3. Compute MD5 and dedup on (configuration_id, md5).
  4. Create the Document (status=pending) + IngestionLog rows.
  5. Dispatch the Celery chain parse -> chunk -> embed and record the root id.

Heavy / cross-subtree imports (boto3, celery, workers.tasks) are done lazily
inside the methods so this module stays importable on its own.
"""
from __future__ import annotations

import asyncio
import hashlib
import uuid

import structlog
from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.repositories.configuration_repo import ConfigurationRepository
from app.repositories.document_repo import DocumentRepository
from app.repositories.ingestion_log_repo import IngestionLogRepository
from app.repositories.vector_repo import AsyncVectorRepository
from app.schemas.ingest import IngestDocumentRequest, IngestDocumentResponse
from app.schemas.status import DocumentStatusResponse, StageStatus, TaskStatusResponse

logger = structlog.get_logger(__name__)


def _metadata_with_organization(
    metadata: dict | None,
    *,
    organization_id: uuid.UUID,
) -> dict:
    """Return metadata stamped with the trusted top-level organization scope."""
    normalized = dict(metadata or {})
    requested_value = str(organization_id)
    existing_value = normalized.get("organization_id")
    if existing_value not in (None, requested_value):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="metadata.organization_id must match organization_id",
        )
    normalized["organization_id"] = requested_value
    return normalized


def _metadata_from_ingest_request(req: IngestDocumentRequest) -> dict:
    metadata = {
        **req.metadata_tags,
        "organization_id": str(req.organization_id),
        "playbook_document_id": str(req.playbook_document_id),
        "source_title": req.source_title,
        "source_date": req.source_date.isoformat() if req.source_date else None,
        "is_official": True,
        "priority": 0,
        "visibility_policy": req.visibility_policy,
        "metadata_tags": req.metadata_tags,
        "content_type": req.content_type,
        "size_bytes": req.size_bytes,
        "status_webhook_url": req.status_webhook_url,
        "webhook_enabled": bool(req.status_webhook_url),
    }
    return _metadata_with_organization(metadata, organization_id=req.organization_id)


def _playbook_document_id(metadata: dict | None) -> uuid.UUID | None:
    value = (metadata or {}).get("playbook_document_id")
    if value in (None, ""):
        return None
    try:
        return uuid.UUID(str(value))
    except (TypeError, ValueError):
        return None


def _delete_s3_object(s3_key: str) -> None:
    """Synchronous S3 deletion — intended to run via asyncio.to_thread."""
    from app.core.config import settings
    from app.infrastructure.io.s3_tempfile import build_s3_client

    client = build_s3_client()
    try:
        client.delete_object(Bucket=settings.S3_BUCKET_NAME, Key=s3_key)
        logger.info("kb_s3_object_deleted", s3_key=s3_key)
    except Exception as exc:
        logger.warning("kb_s3_delete_failed", s3_key=s3_key, error=str(exc))


class IngestionService:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session
        self._config_repo = ConfigurationRepository(session)
        self._doc_repo = DocumentRepository(session)
        self._log_repo = IngestionLogRepository(session)
        self._vector_repo = AsyncVectorRepository(session)

    async def _compute_s3_object_md5(self, s3_key: str) -> str:
        return await asyncio.to_thread(self._compute_s3_object_md5_sync, s3_key)

    async def _enforce_max_size(self, s3_key: str) -> None:
        """HEAD the S3 object and reject early if it exceeds KB_MAX_DOCUMENT_SIZE_MB.

        Cheaper than the MD5 download (which streams the full object), so check first.
        """
        from app.core.config import settings

        size_bytes = await asyncio.to_thread(self._head_s3_object_size_sync, s3_key)
        max_bytes = settings.KB_MAX_DOCUMENT_SIZE_MB * 1024 * 1024
        if size_bytes > max_bytes:
            mb = size_bytes / (1024 * 1024)
            raise HTTPException(
                status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                detail=(
                    f"Document exceeds maximum size of {settings.KB_MAX_DOCUMENT_SIZE_MB} MB "
                    f"(received {mb:.1f} MB). Split the document or contact the KB admin."
                ),
            )

    def _head_s3_object_size_sync(self, s3_key: str) -> int:
        from botocore.exceptions import ClientError

        from app.core.config import settings
        from app.infrastructure.io.s3_tempfile import (
            build_s3_client,
            invalidate_s3_client,
        )

        for attempt in range(2):
            try:
                response = build_s3_client().head_object(
                    Bucket=settings.S3_BUCKET_NAME, Key=s3_key
                )
                return int(response.get("ContentLength", 0))
            except ClientError as exc:
                if exc.response["Error"]["Code"] in ("ExpiredToken", "InvalidClientTokenId") and attempt == 0:
                    invalidate_s3_client()
                    continue
                raise
        raise RuntimeError("HEAD failed after credential refresh")

    def _compute_s3_object_md5_sync(self, s3_key: str) -> str:
        from botocore.exceptions import ClientError

        from app.core.config import settings
        from app.infrastructure.io.s3_tempfile import (
            build_s3_client,
            invalidate_s3_client,
        )

        for attempt in range(2):
            try:
                md5_hash = hashlib.md5()  # noqa: S324
                response = build_s3_client().get_object(Bucket=settings.S3_BUCKET_NAME, Key=s3_key)
                body = response["Body"]
                try:
                    while True:
                        chunk = body.read(8 * 1024 * 1024)
                        if not chunk:
                            break
                        md5_hash.update(chunk)
                finally:
                    body.close()
                return md5_hash.hexdigest()
            except ClientError as exc:
                if exc.response["Error"]["Code"] in ("ExpiredToken", "InvalidClientTokenId") and attempt == 0:
                    invalidate_s3_client()
                    continue
                raise
        raise RuntimeError("MD5 computation failed after credential refresh")

    _IN_PROGRESS_STATUSES = frozenset({"pending", "parsing", "chunking", "embedding", "loading"})

    async def start_ingest(self, req: IngestDocumentRequest) -> IngestDocumentResponse:
        from app.infrastructure.io.s3_tempfile import extract_s3_parts

        config = await self._config_repo.get(req.configuration_id)
        if not config:
            raise LookupError(f"Configuration {req.configuration_id} not found")
        metadata = _metadata_from_ingest_request(req)

        _, s3_key = extract_s3_parts(req.source_uri)
        # Enforce max document size BEFORE MD5 download — HEAD is cheap, MD5 streams full bytes.
        await self._enforce_max_size(s3_key)
        md5 = await self._compute_s3_object_md5(s3_key)

        existing = await self._doc_repo.get_by_config_and_md5(req.configuration_id, md5)

        if existing:
            existing_organization_id = (existing.metadata_ or {}).get("organization_id")
            if existing_organization_id != str(req.organization_id):
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail=(
                        "document content already exists for a different organization"
                    ),
                )
            if existing.status in self._IN_PROGRESS_STATUSES:
                # Pipeline already running — return existing task_id, don't dispatch a duplicate.
                log = await self._log_repo.get_by_document(existing.id)
                logger.info("kb_ingest_skipped_in_progress", doc_id=str(existing.id), doc_status=existing.status)
                return IngestDocumentResponse(
                    kb_service_document_id=existing.id,
                    playbook_document_id=req.playbook_document_id,
                    task_id=log.pipeline_task_id if log else None,
                    status=existing.status,
                )

            # success or failed — delete the old record and start fresh.
            logger.info("kb_ingest_replacing", doc_id=str(existing.id), prev_status=existing.status)
            await self._vector_repo.delete_document_embeddings(existing.id)
            await self._doc_repo.delete(existing.id)

        # Create a new document record (fresh doc_id each time).
        doc_id = uuid.uuid4()

        # Guard: caller-supplied ID must not collide with a different document.
        await self._doc_repo.create(
            document_id=doc_id,
            configuration_id=req.configuration_id,
            name=req.filename,
            md5=md5,
            s3_key=s3_key,
            metadata=metadata,
        )
        await self._log_repo.create(doc_id)

        task_id = await self._dispatch_pipeline(doc_id, config, s3_key, req.filename, metadata)
        logger.info("kb_ingest_dispatched", doc_id=str(doc_id), task_id=task_id, s3_key=s3_key)
        return IngestDocumentResponse(
            kb_service_document_id=doc_id,
            playbook_document_id=req.playbook_document_id,
            task_id=task_id,
            status="pending",
        )

    async def _dispatch_pipeline(
        self,
        document_id: uuid.UUID,
        config,
        s3_key: str,
        filename: str,
        metadata: dict,
    ) -> str:
        # Lazy import: the workers package is built by another agent. Importing
        # it here (not at module top) keeps this module importable on its own.
        from app.workers.tasks import chunk_task, embed_task, parse_task

        pipeline = parse_task.s(
            document_id=str(document_id),
            s3_key=s3_key,
            filename=filename,
            config_id=str(config.id),
        ) | chunk_task.s(
            document_id=str(document_id),
            metadata=metadata,
        ) | embed_task.s(
            document_id=str(document_id),
            config_id=str(config.id),
        )
        result = pipeline.apply_async()
        root_task_id = result.id
        await self._log_repo.set_root_task_id(document_id, root_task_id)
        return root_task_id

    async def get_task_status(self, task_id: str) -> TaskStatusResponse:
        from celery.result import AsyncResult

        from app.workers.app import kb_worker

        task_result = AsyncResult(task_id, app=kb_worker)
        ingestion_log = await self._log_repo.get_by_any_task_id(task_id)
        if ingestion_log is None:
            return TaskStatusResponse(
                task_id=task_id,
                document_id=None,
                celery_state=task_result.state,
                stages=[
                    StageStatus(stage="parse", status=None, task_id=None),
                    StageStatus(stage="chunk", status=None, task_id=None),
                    StageStatus(stage="embed", status=None, task_id=None),
                    StageStatus(stage="load_vector", status=None, task_id=None),
                ],
            )

        return TaskStatusResponse(
            task_id=task_id,
            document_id=ingestion_log.document_id,
            celery_state=task_result.state,
            stages=[
                StageStatus(
                    stage="parse",
                    status=ingestion_log.parse_status,
                    task_id=ingestion_log.parse_task_id,
                ),
                StageStatus(
                    stage="chunk",
                    status=ingestion_log.chunk_status,
                    task_id=ingestion_log.chunk_task_id,
                ),
                StageStatus(
                    stage="embed",
                    status=ingestion_log.embed_status,
                    task_id=ingestion_log.embed_task_id,
                ),
                StageStatus(
                    stage="load_vector",
                    status=ingestion_log.load_vector_status,
                    task_id=ingestion_log.load_vector_task_id,
                ),
            ],
            error_message=ingestion_log.error_message,
            updated_at=ingestion_log.updated_at,
        )

    async def get_document_status(self, document_id: uuid.UUID) -> DocumentStatusResponse:
        doc = await self._doc_repo.get(document_id)
        if doc is None:
            raise LookupError(f"Document {document_id} not found")
        log = await self._log_repo.get_by_document(document_id)
        stages = [
            StageStatus(stage="parse", status=None, task_id=None),
            StageStatus(stage="chunk", status=None, task_id=None),
            StageStatus(stage="embed", status=None, task_id=None),
            StageStatus(stage="load_vector", status=None, task_id=None),
        ]
        task_id = None
        error_message = None
        updated_at = doc.updated_at
        if log is not None:
            stages = [
                StageStatus(stage="parse", status=log.parse_status, task_id=log.parse_task_id),
                StageStatus(stage="chunk", status=log.chunk_status, task_id=log.chunk_task_id),
                StageStatus(stage="embed", status=log.embed_status, task_id=log.embed_task_id),
                StageStatus(
                    stage="load_vector",
                    status=log.load_vector_status,
                    task_id=log.load_vector_task_id,
                ),
            ]
            task_id = log.pipeline_task_id
            error_message = log.error_message
            updated_at = log.updated_at
        return DocumentStatusResponse(
            kb_service_document_id=doc.id,
            playbook_document_id=_playbook_document_id(doc.metadata_),
            task_id=task_id,
            status=doc.status,
            stages=stages,
            error_message=error_message,
            updated_at=updated_at,
        )

    async def retry_document(self, document_id: uuid.UUID) -> IngestDocumentResponse:
        doc = await self._doc_repo.get(document_id)
        if doc is None:
            raise LookupError(f"Document {document_id} not found")
        config = await self._config_repo.get(doc.configuration_id)
        if not config:
            raise LookupError(f"Configuration {doc.configuration_id} not found")

        await self._vector_repo.delete_document_embeddings(document_id)
        await self._doc_repo.update_status(document_id, "pending")
        if await self._log_repo.get_by_document(document_id) is None:
            await self._log_repo.create(document_id)
        task_id = await self._dispatch_pipeline(
            document_id,
            config,
            doc.s3_key,
            doc.name,
            doc.metadata_ or {},
        )
        logger.info("kb_ingest_retry_dispatched", doc_id=str(document_id), task_id=task_id)
        return IngestDocumentResponse(
            kb_service_document_id=document_id,
            playbook_document_id=_playbook_document_id(doc.metadata_) or document_id,
            task_id=task_id,
            status="pending",
        )

    async def delete_document(self, document_id: uuid.UUID) -> None:
        doc = await self._doc_repo.get(document_id)

        # Delete embeddings first — explicit commit inside delete_document_embeddings
        # so the vector delete is never deferred or accidentally rolled back.
        deleted_embeddings = await self._vector_repo.delete_document_embeddings(document_id)

        # Delete document record (cascades to ingestion_log); idempotent if already gone
        await self._doc_repo.delete(document_id)

        # S3 deletion is best-effort: run in thread pool so we don't block the event loop
        if doc and doc.s3_key:
            await asyncio.to_thread(_delete_s3_object, doc.s3_key)

        logger.info("kb_document_deleted", doc_id=str(document_id), embeddings_deleted=deleted_embeddings)
