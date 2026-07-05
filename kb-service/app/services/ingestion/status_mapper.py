"""DTO mapping helpers for ingestion responses and status endpoints."""

from __future__ import annotations

import uuid
from typing import Any

from app.schemas.ingest import IngestDocumentResponse
from app.schemas.status import DocumentStatusResponse, StageStatus, TaskStatusResponse

_STAGE_NAMES = ("parse", "chunk", "summarize", "embed", "load_vector")


def uuid_from_metadata(metadata: dict[str, Any] | None, key: str) -> uuid.UUID | None:
    value = (metadata or {}).get(key)
    if value in (None, ""):
        return None
    try:
        return uuid.UUID(str(value))
    except (TypeError, ValueError):
        return None


def playbook_document_id_from_metadata(
    metadata: dict[str, Any] | None,
) -> uuid.UUID | None:
    return uuid_from_metadata(metadata, "playbook_document_id")


def conversation_id_from_metadata(metadata: dict[str, Any] | None) -> uuid.UUID | None:
    return uuid_from_metadata(metadata, "conversation_id")


def conversation_file_id_from_metadata(
    metadata: dict[str, Any] | None,
) -> uuid.UUID | None:
    return uuid_from_metadata(metadata, "conversation_file_id")


def default_stage_statuses() -> list[StageStatus]:
    return [
        StageStatus(stage=stage, status=None, task_id=None)
        for stage in _STAGE_NAMES
    ]


def stage_statuses_from_log(log: Any) -> list[StageStatus]:
    return [
        StageStatus(
            stage="parse",
            status=getattr(log, "parse_status", None),
            task_id=getattr(log, "parse_task_id", None),
        ),
        StageStatus(
            stage="chunk",
            status=getattr(log, "chunk_status", None),
            task_id=getattr(log, "chunk_task_id", None),
        ),
        StageStatus(
            stage="summarize",
            status=getattr(log, "summarize_status", None),
            task_id=getattr(log, "summarize_task_id", None),
        ),
        StageStatus(
            stage="embed",
            status=getattr(log, "embed_status", None),
            task_id=getattr(log, "embed_task_id", None),
        ),
        StageStatus(
            stage="load_vector",
            status=getattr(log, "load_vector_status", None),
            task_id=getattr(log, "load_vector_task_id", None),
        ),
    ]


def ingest_response(
    *,
    kb_service_document_id: uuid.UUID,
    metadata: dict[str, Any] | None,
    task_id: str | None,
    status_: str,
    fallback_playbook_document_id: uuid.UUID | None = None,
) -> IngestDocumentResponse:
    metadata = metadata or {}
    source_type = metadata.get("source_type", "admin_upload")
    playbook_document_id = playbook_document_id_from_metadata(metadata)
    if source_type == "admin_upload" and playbook_document_id is None:
        playbook_document_id = fallback_playbook_document_id
    return IngestDocumentResponse(
        kb_service_document_id=kb_service_document_id,
        source_type=source_type,
        playbook_document_id=playbook_document_id,
        conversation_id=conversation_id_from_metadata(metadata),
        conversation_file_id=conversation_file_id_from_metadata(metadata),
        task_id=task_id,
        status=status_,
    )


def task_status_response(
    *,
    task_id: str,
    celery_state: str | None,
    ingestion_log: Any | None,
) -> TaskStatusResponse:
    if ingestion_log is None:
        return TaskStatusResponse(
            task_id=task_id,
            document_id=None,
            celery_state=celery_state,
            stages=default_stage_statuses(),
        )

    return TaskStatusResponse(
        task_id=task_id,
        document_id=ingestion_log.document_id,
        celery_state=celery_state,
        stages=stage_statuses_from_log(ingestion_log),
        error_message=ingestion_log.error_message,
        updated_at=ingestion_log.updated_at,
    )


def document_status_response(*, doc: Any, log: Any | None) -> DocumentStatusResponse:
    stages = default_stage_statuses()
    task_id = None
    error_message = None
    updated_at = doc.updated_at
    if log is not None:
        stages = stage_statuses_from_log(log)
        task_id = log.pipeline_task_id
        error_message = log.error_message
        updated_at = log.updated_at
    return DocumentStatusResponse(
        kb_service_document_id=doc.id,
        playbook_document_id=playbook_document_id_from_metadata(doc.metadata_),
        task_id=task_id,
        status=doc.status,
        summary=getattr(doc, "summary", None),
        stages=stages,
        error_message=error_message,
        updated_at=updated_at,
    )
