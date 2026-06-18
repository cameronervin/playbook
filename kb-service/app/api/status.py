"""Document status contract endpoints."""
from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status

from app.api.deps.services import get_ingestion_service
from app.schemas.status import DocumentStatusResponse
from app.services.ingestion import IngestionService

router = APIRouter()


@router.get("/documents/{document_id}", response_model=DocumentStatusResponse)
async def get_document_status(
    document_id: uuid.UUID,
    svc: Annotated[IngestionService, Depends(get_ingestion_service)],
) -> DocumentStatusResponse:
    """Return KB-service document status and per-stage breakdown."""
    try:
        return await svc.get_document_status(document_id)
    except LookupError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
