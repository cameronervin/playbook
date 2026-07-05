"""Document contract endpoints."""
from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Response, status

from app.api.deps.services import get_ingestion_service
from app.schemas.ingest import (
    DocumentMetadataRefreshRequest,
    DocumentMetadataRefreshResponse,
    IngestDocumentResponse,
)
from app.services.ingestion import IngestionService

router = APIRouter()


@router.post("/{document_id}/retry", response_model=IngestDocumentResponse)
async def retry_document(
    document_id: uuid.UUID,
    svc: Annotated[IngestionService, Depends(get_ingestion_service)],
) -> IngestDocumentResponse:
    """Retry ingestion for an existing KB-service document."""
    try:
        return await svc.retry_document(document_id)
    except LookupError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc


@router.patch("/{document_id}/metadata", response_model=DocumentMetadataRefreshResponse)
async def refresh_document_metadata(
    document_id: uuid.UUID,
    body: DocumentMetadataRefreshRequest,
    svc: Annotated[IngestionService, Depends(get_ingestion_service)],
) -> DocumentMetadataRefreshResponse:
    """Refresh document and vector metadata without re-embedding."""
    try:
        return await svc.refresh_document_metadata(document_id, body)
    except LookupError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc


@router.delete("/{document_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_document(
    document_id: uuid.UUID,
    svc: Annotated[IngestionService, Depends(get_ingestion_service)],
) -> Response:
    """Delete document record and all associated embeddings from kb.langchain_pg_embedding.
    Idempotent — returns 204 even if the document does not exist."""
    await svc.delete_document(document_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
