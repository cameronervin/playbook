"""Document API — list and delete endpoints."""
from __future__ import annotations

import uuid
from typing import Any

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps.services import get_ingestion_service
from app.db.session import get_db
from app.repositories.document_repo import DocumentRepository
from app.services.ingestion_service import IngestionService

router = APIRouter()


@router.get("/", response_model=list[dict[str, Any]])
async def list_documents(
    configuration_id: uuid.UUID = Query(...),
    filename: str | None = Query(None),
    db: AsyncSession = Depends(get_db),
) -> list[dict[str, Any]]:
    repo = DocumentRepository(db)
    docs = await repo.find_by_name(configuration_id, filename) if filename else []
    return [{"id": str(doc.id), "name": doc.name, "status": doc.status} for doc in docs]


@router.delete("/{document_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_document(
    document_id: uuid.UUID,
    svc: IngestionService = Depends(get_ingestion_service),
) -> None:
    """Delete document record and all associated embeddings from kb.langchain_pg_embedding.
    Idempotent — returns 204 even if the document does not exist."""
    await svc.delete_document(document_id)
