"""POST /api/kb/embed/search — semantic similarity search.

Mounted under the /embed prefix, so the full path is /api/kb/embed/search.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status

from app.api.deps.services import get_search_service
from app.schemas.search import SearchRequest, SearchResponse
from app.services.search_service import SearchService

router = APIRouter()


@router.post("/search", response_model=SearchResponse)
async def embed_search(
    body: SearchRequest,
    svc: SearchService = Depends(get_search_service),
) -> SearchResponse:
    try:
        return await svc.search(body)
    except LookupError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))
