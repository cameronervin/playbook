"""Admin KB document routes."""

from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Query, Request, status
from fastapi.responses import Response

from app.api.v1.dependencies import (
    AdminUserDep,
    KBDocumentServiceDep,
    RateLimitServiceDep,
)
from app.schemas.kb_documents import (
    KBDocumentMetadataUpdateRequest,
    KBDocumentResponse,
    KBDocumentStatus,
    KBDocumentUploadRequest,
    KBDocumentUploadRequestResponse,
)
from app.schemas.uploads import UploadCompleteRequest
from app.services.rate_limit import RateLimitPolicy

router = APIRouter(prefix="/admin/kb/documents", tags=["KB Documents"])


@router.get("", response_model=list[KBDocumentResponse])
async def list_documents(
    http_request: Request,
    actor: AdminUserDep,
    service: KBDocumentServiceDep,
    rate_limiter: RateLimitServiceDep,
    processing_status: KBDocumentStatus | None = None,
    limit: Annotated[int, Query(ge=1, le=500)] = 100,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> list[KBDocumentResponse]:
    """List organization KB documents."""
    await rate_limiter.enforce(
        RateLimitPolicy.LIST,
        request=http_request,
        user=actor,
    )
    return await service.list_documents(
        actor=actor,
        processing_status=processing_status,
        limit=limit,
        offset=offset,
    )


@router.post(
    "",
    response_model=KBDocumentUploadRequestResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_upload_request(
    payload: KBDocumentUploadRequest,
    http_request: Request,
    actor: AdminUserDep,
    service: KBDocumentServiceDep,
    rate_limiter: RateLimitServiceDep,
) -> KBDocumentUploadRequestResponse:
    """Create a shared KB document direct-upload request."""
    await rate_limiter.enforce(
        RateLimitPolicy.UPLOAD,
        request=http_request,
        user=actor,
    )
    return await service.create_upload_request(actor=actor, request=payload)


@router.post("/{document_id}/upload-complete", response_model=KBDocumentResponse)
async def complete_upload(
    document_id: UUID,
    payload: UploadCompleteRequest,
    http_request: Request,
    actor: AdminUserDep,
    service: KBDocumentServiceDep,
    rate_limiter: RateLimitServiceDep,
) -> KBDocumentResponse:
    """Verify an uploaded KB document object and queue ingestion."""
    await rate_limiter.enforce(
        RateLimitPolicy.UPLOAD,
        request=http_request,
        user=actor,
    )
    return await service.complete_upload(
        actor=actor,
        document_id=document_id,
        request=payload,
    )


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
