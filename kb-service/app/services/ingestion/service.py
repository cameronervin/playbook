"""Route-facing ingestion service facade.

Flow of start_ingest:
  1. Resolve the configuration.
  2. HEAD the S3 object to enforce the max-size guard before MD5 download.
  3. Compute MD5 and dedupe by trusted source identity/content.
  4. Create the Document (status=pending) + IngestionLog rows.
  5. Dispatch the Celery chain parse -> chunk -> summarize -> embed.

Heavy / cross-subtree imports (boto3, celery, workers.tasks) remain lazy in the
focused helper modules so this route-facing service stays importable on its own.
"""

from __future__ import annotations

import asyncio
import uuid
from typing import Any

import structlog
from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.repositories.configuration_repo import ConfigurationRepository
from app.repositories.document_repo import DocumentRepository
from app.repositories.ingestion_log_repo import IngestionLogRepository
from app.repositories.vector_repo import AsyncVectorRepository
from app.schemas.ingest import (
    DocumentMetadataRefreshRequest,
    DocumentMetadataRefreshResponse,
    IngestDocumentRequest,
    IngestDocumentResponse,
)
from app.schemas.status import DocumentStatusResponse, TaskStatusResponse
from app.services.ingestion.metadata import (
    IngestRequest,
    metadata_from_ingest_request,
    metadata_with_organization,
)
from app.services.ingestion.pipeline_dispatcher import IngestionPipelineDispatcher
from app.services.ingestion.s3_inspector import S3ObjectInspector, delete_s3_object
from app.services.ingestion.source_identity import (
    SOURCE_IDENTITY_CONFLICT_DETAIL,
    SourceIdentityResolver,
    dedupe_md5_for_ingest_request,
    metadata_matches_trusted_source_identity,
)
from app.services.ingestion.status_mapper import (
    conversation_file_id_from_metadata,
    conversation_id_from_metadata,
    document_status_response,
    ingest_response,
    playbook_document_id_from_metadata,
    task_status_response,
)

logger = structlog.get_logger(__name__)

# Compatibility aliases for existing imports and tests. New code should import
# from app.services.ingestion.* focused modules instead.
_metadata_with_organization = metadata_with_organization
_metadata_from_ingest_request = metadata_from_ingest_request
_dedupe_md5_for_ingest_request = dedupe_md5_for_ingest_request
_metadata_matches_trusted_source_identity = metadata_matches_trusted_source_identity
_playbook_document_id = playbook_document_id_from_metadata
_conversation_id = conversation_id_from_metadata
_conversation_file_id = conversation_file_id_from_metadata
_ingest_response = ingest_response
_delete_s3_object = delete_s3_object
_SOURCE_IDENTITY_CONFLICT_DETAIL = SOURCE_IDENTITY_CONFLICT_DETAIL


def _refreshed_admin_upload_metadata(
    existing_metadata: dict[str, Any],
    req: DocumentMetadataRefreshRequest,
) -> dict[str, Any]:
    """Return refreshed metadata for an existing admin-upload document."""
    if existing_metadata.get("source_type") != "admin_upload":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="metadata refresh is only supported for admin_upload documents",
        )

    metadata = dict(existing_metadata)
    old_metadata_tags = metadata.get("metadata_tags")
    if isinstance(old_metadata_tags, dict):
        for key in old_metadata_tags:
            metadata.pop(str(key), None)

    metadata_tags = dict(req.metadata_tags)
    metadata.update(metadata_tags)
    metadata.update(
        {
            "source_date": req.source_date.isoformat() if req.source_date else None,
            "is_official": True,
            "priority": 0,
            "visibility_policy": req.visibility_policy,
            "metadata_tags": metadata_tags,
        }
    )
    return metadata


def _metadata_refresh_stale_keys(
    existing_metadata: dict[str, Any],
    refreshed_metadata: dict[str, Any],
) -> set[str]:
    stale_keys = set(refreshed_metadata)
    old_metadata_tags = existing_metadata.get("metadata_tags")
    if isinstance(old_metadata_tags, dict):
        stale_keys.update(str(key) for key in old_metadata_tags)
    return stale_keys


def _metadata_refresh_request_from_admin_ingest(
    req: IngestDocumentRequest,
) -> DocumentMetadataRefreshRequest:
    """Project an admin ingest request onto mutable retrieval metadata fields."""
    return DocumentMetadataRefreshRequest(
        source_date=req.source_date,
        is_official=True,
        priority=0,
        visibility_policy=req.visibility_policy,
        metadata_tags=req.metadata_tags,
    )


def _delete_pages_staging(document_id: str) -> None:
    from app.workers.tasks.staging import _delete_pages_staging as delete_pages_staging

    delete_pages_staging(document_id)


def _delete_staging_file(document_id: str) -> None:
    from app.workers.tasks.staging import _delete_staging_file as delete_staging_file

    delete_staging_file(document_id)


class IngestionService:
    _IN_PROGRESS_STATUSES = frozenset(
        {"pending", "parsing", "chunking", "embedding", "loading"}
    )

    def __init__(self, session: AsyncSession) -> None:
        self._session = session
        self._config_repo = ConfigurationRepository(session)
        self._doc_repo = DocumentRepository(session)
        self._log_repo = IngestionLogRepository(session)
        self._vector_repo = AsyncVectorRepository(session)
        self._source_identity = SourceIdentityResolver(self._doc_repo)
        self._s3_inspector = S3ObjectInspector()
        self._pipeline_dispatcher = IngestionPipelineDispatcher(self._log_repo)

    async def _compute_s3_object_md5(self, s3_key: str) -> str:
        return await self._s3_inspector.compute_s3_object_md5(s3_key)

    async def _enforce_max_size(self, s3_key: str) -> None:
        await self._s3_inspector.enforce_max_size(s3_key)

    def _head_s3_object_size_sync(self, s3_key: str) -> int:
        return self._s3_inspector.head_s3_object_size_sync(s3_key)

    def _compute_s3_object_md5_sync(self, s3_key: str) -> str:
        return self._s3_inspector.compute_s3_object_md5_sync(s3_key)

    async def start_ingest(self, req: IngestRequest) -> IngestDocumentResponse:
        from app.infrastructure.io.s3_tempfile import extract_s3_parts

        config = await self._config_repo.get(req.configuration_id)
        if not config:
            raise LookupError(f"Configuration {req.configuration_id} not found")
        metadata = metadata_from_ingest_request(req)

        existing_source = await self._get_existing_source_identity_document(req)
        if existing_source is not None:
            return await self._existing_ingest_response(
                existing_source,
                refresh_from_request=req,
                fallback_playbook_document_id=req.playbook_document_id
                if isinstance(req, IngestDocumentRequest)
                else None,
            )

        _, s3_key = extract_s3_parts(req.source_uri)
        await self._enforce_max_size(s3_key)
        raw_md5 = await self._compute_s3_object_md5(s3_key)
        md5 = dedupe_md5_for_ingest_request(req, raw_md5)
        metadata["raw_content_md5"] = raw_md5

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
            if not metadata_matches_trusted_source_identity(existing.metadata_, req):
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail=SOURCE_IDENTITY_CONFLICT_DETAIL,
                )
            return await self._existing_ingest_response(
                existing,
                refresh_from_request=req,
                fallback_playbook_document_id=req.playbook_document_id
                if isinstance(req, IngestDocumentRequest)
                else None,
            )

        doc_id = uuid.uuid4()
        await self._doc_repo.create(
            document_id=doc_id,
            configuration_id=req.configuration_id,
            name=req.filename,
            md5=md5,
            s3_key=s3_key,
            metadata=metadata,
        )
        await self._log_repo.create(doc_id)

        task_id = await self._dispatch_pipeline(
            doc_id, config, s3_key, req.filename, metadata
        )
        logger.info(
            "kb_ingest_dispatched",
            doc_id=str(doc_id),
            task_id=task_id,
            s3_key=s3_key,
        )
        return ingest_response(
            kb_service_document_id=doc_id,
            metadata=metadata,
            task_id=task_id,
            status_="pending",
        )

    async def _get_existing_source_identity_document(
        self,
        req: IngestRequest,
    ) -> Any | None:
        resolver = getattr(
            self,
            "_source_identity",
            SourceIdentityResolver(self._doc_repo),
        )
        return await resolver.get_existing_document(req)

    async def _existing_ingest_response(
        self,
        existing: Any,
        *,
        refresh_from_request: IngestRequest | None = None,
        fallback_playbook_document_id: uuid.UUID | None = None,
    ) -> IngestDocumentResponse:
        task_id = None
        if existing.status in self._IN_PROGRESS_STATUSES:
            log = await self._log_repo.get_by_document(existing.id)
            task_id = log.pipeline_task_id if log else None
        metadata = existing.metadata_
        if isinstance(refresh_from_request, IngestDocumentRequest):
            metadata = await self._refresh_existing_admin_upload_metadata(
                existing,
                refresh_from_request,
            )
        logger.info(
            "kb_ingest_duplicate_source_identity",
            doc_id=str(existing.id),
            doc_status=existing.status,
            source_type=(metadata or {}).get("source_type"),
            active=existing.status in self._IN_PROGRESS_STATUSES,
        )
        return ingest_response(
            kb_service_document_id=existing.id,
            metadata=metadata,
            task_id=task_id,
            status_=existing.status,
            fallback_playbook_document_id=fallback_playbook_document_id,
        )

    async def _refresh_existing_admin_upload_metadata(
        self,
        existing: Any,
        req: IngestDocumentRequest,
    ) -> dict[str, Any]:
        existing_metadata = existing.metadata_ or {}
        metadata = _refreshed_admin_upload_metadata(
            existing_metadata,
            _metadata_refresh_request_from_admin_ingest(req),
        )
        stale_keys = _metadata_refresh_stale_keys(existing_metadata, metadata)
        updated = await self._doc_repo.update_metadata(existing.id, metadata)
        await self._vector_repo.refresh_document_metadata(
            existing.id,
            metadata,
            stale_metadata_keys=stale_keys,
        )
        return (updated.metadata_ if updated is not None else metadata) or metadata

    async def _dispatch_pipeline(
        self,
        document_id: uuid.UUID,
        config: Any,
        s3_key: str,
        filename: str,
        metadata: dict[str, Any],
    ) -> str:
        dispatcher = getattr(
            self,
            "_pipeline_dispatcher",
            IngestionPipelineDispatcher(self._log_repo),
        )
        return await dispatcher.dispatch(document_id, config, s3_key, filename, metadata)

    async def get_task_status(self, task_id: str) -> TaskStatusResponse:
        from celery.result import AsyncResult

        from app.workers.app import kb_worker

        task_result = AsyncResult(task_id, app=kb_worker)
        ingestion_log = await self._log_repo.get_by_any_task_id(task_id)
        return task_status_response(
            task_id=task_id,
            celery_state=task_result.state,
            ingestion_log=ingestion_log,
        )

    async def get_document_status(self, document_id: uuid.UUID) -> DocumentStatusResponse:
        doc = await self._doc_repo.get(document_id)
        if doc is None:
            raise LookupError(f"Document {document_id} not found")
        log = await self._log_repo.get_by_document(document_id)
        return document_status_response(doc=doc, log=log)

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
        else:
            await self._log_repo.reset_for_retry(document_id)
        task_id = await self._dispatch_pipeline(
            document_id,
            config,
            doc.s3_key,
            doc.name,
            doc.metadata_ or {},
        )
        logger.info(
            "kb_ingest_retry_dispatched",
            doc_id=str(document_id),
            task_id=task_id,
        )
        return ingest_response(
            kb_service_document_id=document_id,
            metadata=doc.metadata_,
            task_id=task_id,
            status_="pending",
            fallback_playbook_document_id=document_id,
        )

    async def refresh_document_metadata(
        self,
        document_id: uuid.UUID,
        req: DocumentMetadataRefreshRequest,
    ) -> DocumentMetadataRefreshResponse:
        doc = await self._doc_repo.get(document_id)
        if doc is None:
            raise LookupError(f"Document {document_id} not found")

        existing_metadata = doc.metadata_ or {}
        metadata = _refreshed_admin_upload_metadata(existing_metadata, req)
        stale_keys = _metadata_refresh_stale_keys(existing_metadata, metadata)
        updated = await self._doc_repo.update_metadata(document_id, metadata)
        if updated is None:
            raise LookupError(f"Document {document_id} not found")
        updated_embedding_count = await self._vector_repo.refresh_document_metadata(
            document_id,
            metadata,
            stale_metadata_keys=stale_keys,
        )
        logger.info(
            "kb_document_metadata_refreshed",
            doc_id=str(document_id),
            source_type=metadata.get("source_type"),
            updated_embedding_count=updated_embedding_count,
        )
        return DocumentMetadataRefreshResponse(
            kb_service_document_id=document_id,
            source_type="admin_upload",
            playbook_document_id=playbook_document_id_from_metadata(metadata),
            updated_embedding_count=updated_embedding_count,
            metadata=metadata,
        )

    async def delete_document(self, document_id: uuid.UUID) -> None:
        doc = await self._doc_repo.get(document_id)

        deleted_embeddings = await self._vector_repo.delete_document_embeddings(
            document_id
        )
        await self._doc_repo.delete(document_id)
        document_id_text = str(document_id)

        if doc and doc.s3_key:
            await asyncio.to_thread(delete_s3_object, doc.s3_key)
        await asyncio.to_thread(_delete_pages_staging, document_id_text)
        await asyncio.to_thread(_delete_staging_file, document_id_text)

        logger.info(
            "kb_document_deleted",
            doc_id=str(document_id),
            embeddings_deleted=deleted_embeddings,
        )
