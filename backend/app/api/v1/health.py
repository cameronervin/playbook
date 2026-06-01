"""Health check."""
from fastapi import APIRouter

router = APIRouter(tags=["Health"])


@router.get("/health", summary="API health check")
async def health() -> dict[str, str]:
    return {"status": "healthy"}
