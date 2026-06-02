"""POST /api/kb/ingest/url — start document ingestion."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Response, status

from app.api.deps.services import get_ingestion_service
from app.schemas.ingest import IngestURLRequest, IngestURLResponse
from app.services.ingestion_service import IngestionService

router = APIRouter()


@router.post("/url", response_model=IngestURLResponse, status_code=status.HTTP_202_ACCEPTED)
async def ingest_url(
    body: IngestURLRequest,
    svc: IngestionService = Depends(get_ingestion_service),
) -> Response:
    """Accept a presigned S3 URL, validate the config, create a document record,
    and dispatch the Celery task chain. Returns 202 with task_id immediately
    (200 if the document was already in progress and no new task was dispatched)."""
    try:
        result = await svc.start_ingest(body)
        status_code = status.HTTP_200_OK if result.task_id is None else status.HTTP_202_ACCEPTED
        return Response(status_code=status_code, media_type="application/json", content=result.model_dump_json())
    except HTTPException:
        raise
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))
    except LookupError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))
