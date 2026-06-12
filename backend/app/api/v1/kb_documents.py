"""Admin KB document routes."""

from __future__ import annotations

import json
from datetime import date
from typing import Annotated, Any
from uuid import UUID

from fastapi import APIRouter, File, Form, Query, UploadFile, status
from fastapi.responses import Response

from app.api.v1.dependencies import AdminUserDep, KBDocumentServiceDep
from app.core.exceptions import ValidationError
from app.schemas.kb_documents import (
    KBDocumentMetadataUpdateRequest,
    KBDocumentResponse,
    KBDocumentStatus,
)
from app.services.kb_document_service import KBDocumentUpload

router = APIRouter(prefix="/admin/kb/documents", tags=["KB Documents"])


def _metadata_tags_from_form(metadata_tags: str | None) -> dict[str, Any] | None:
    """Parse optional multipart metadata JSON into a dictionary."""
    if metadata_tags is None or metadata_tags.strip() == "":
        return None
    try:
        parsed = json.loads(metadata_tags)
    except json.JSONDecodeError as exc:
        raise ValidationError("metadata_tags must be a JSON object") from exc
    if not isinstance(parsed, dict):
        raise ValidationError("metadata_tags must be a JSON object")
    return parsed


@router.get("", response_model=list[KBDocumentResponse])
async def list_documents(
    actor: AdminUserDep,
    service: KBDocumentServiceDep,
    processing_status: KBDocumentStatus | None = None,
    limit: Annotated[int, Query(ge=1, le=500)] = 100,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> list[KBDocumentResponse]:
    """List organization KB documents."""
    return await service.list_documents(
        actor=actor,
        processing_status=processing_status,
        limit=limit,
        offset=offset,
    )


@router.post(
    "",
    response_model=KBDocumentResponse,
    status_code=status.HTTP_201_CREATED,
)
async def upload_document(
    actor: AdminUserDep,
    service: KBDocumentServiceDep,
    file: Annotated[UploadFile, File()],
    title: Annotated[str | None, Form()] = None,
    metadata_tags: Annotated[
        str | None,
        Form(
            description="JSON object encoded as a string.",
            examples=['{"topic":"nil","source_type":"policy"}'],
        ),
    ] = None,
    source_date: Annotated[date | None, Form()] = None,
) -> KBDocumentResponse:
    """Upload a shared KB document and request ingestion."""
    upload = KBDocumentUpload(
        filename=file.filename or "document",
        content_type=file.content_type or "application/octet-stream",
        file=file.file,
        title=title,
        metadata_tags=_metadata_tags_from_form(metadata_tags),
        source_date=source_date,
    )
    return await service.upload_document(actor=actor, upload=upload)


@router.get("/{document_id}", response_model=KBDocumentResponse)
async def get_document(
    document_id: UUID,
    actor: AdminUserDep,
    service: KBDocumentServiceDep,
) -> KBDocumentResponse:
    """Get one organization KB document."""
    return await service.get_document(actor=actor, document_id=document_id)


@router.patch("/{document_id}/metadata", response_model=KBDocumentResponse)
async def update_metadata(
    document_id: UUID,
    request: KBDocumentMetadataUpdateRequest,
    actor: AdminUserDep,
    service: KBDocumentServiceDep,
) -> KBDocumentResponse:
    """Update KB document metadata."""
    return await service.update_metadata(
        actor=actor,
        document_id=document_id,
        request=request,
    )


@router.post("/{document_id}/retry", response_model=KBDocumentResponse)
async def retry_document(
    document_id: UUID,
    actor: AdminUserDep,
    service: KBDocumentServiceDep,
) -> KBDocumentResponse:
    """Retry KB ingestion for a document."""
    return await service.retry_document(actor=actor, document_id=document_id)


@router.delete("/{document_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_document(
    document_id: UUID,
    actor: AdminUserDep,
    service: KBDocumentServiceDep,
) -> Response:
    """Delete a KB document and its searchable vectors."""
    await service.delete_document(actor=actor, document_id=document_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
