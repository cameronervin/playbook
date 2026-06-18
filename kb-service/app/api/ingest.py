"""Document ingestion contract endpoints."""
from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Response, status

from app.api.deps.services import get_ingestion_service
from app.schemas.ingest import IngestDocumentResponse, IngestSourceRequest
from app.services.ingestion import IngestionService

router = APIRouter()


@router.post(
    "/document",
    response_model=IngestDocumentResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
async def ingest_document(
    body: IngestSourceRequest,
    svc: Annotated[IngestionService, Depends(get_ingestion_service)],
) -> Response:
    """Start ingestion for an admin upload or trusted conversation file."""
    try:
        result = await svc.start_ingest(body)
        status_code = status.HTTP_200_OK if result.task_id is None else status.HTTP_202_ACCEPTED
        return Response(status_code=status_code, media_type="application/json", content=result.model_dump_json())
    except HTTPException:
        raise
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc
    except LookupError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc
