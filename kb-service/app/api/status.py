"""GET /api/kb/status/{task_id} — polling fallback for the caller's reconciler."""
from __future__ import annotations

from fastapi import APIRouter, Depends

from app.api.deps.services import get_ingestion_service
from app.schemas.status import TaskStatusResponse
from app.services.ingestion_service import IngestionService

router = APIRouter()


@router.get("/{task_id}", response_model=TaskStatusResponse)
async def get_task_status(
    task_id: str,
    svc: IngestionService = Depends(get_ingestion_service),
) -> TaskStatusResponse:
    """Return Celery task state + per-stage breakdown from kb.ingestion_logs.
    Used by the caller's reconciler — the webhook is the primary delivery path."""
    return await svc.get_task_status(task_id)
