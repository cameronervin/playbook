"""Top-level API router — mounts all KB sub-routers.

All routes require a valid Bearer token (settings.KB_API_SECRET) from the
calling app, EXCEPT /health which must stay reachable by infra probes without
credentials. The root /health alias in main.py is likewise unauthenticated.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends

from app.api.configuration import router as configuration_router
from app.api.deps.service_auth import verify_service_auth
from app.api.documents import router as documents_router
from app.api.health import router as health_router
from app.api.ingest import router as ingest_router
from app.api.search import router as search_router
from app.api.status import router as status_router

_auth = [Depends(verify_service_auth)]

api_router = APIRouter()

# Health — no auth (must be reachable by infra probes without credentials)
api_router.include_router(health_router, prefix="/health", tags=["health"])

api_router.include_router(configuration_router, prefix="/configuration", tags=["configuration"], dependencies=_auth)
api_router.include_router(ingest_router, prefix="/ingest", tags=["ingest"], dependencies=_auth)
api_router.include_router(status_router, prefix="/status", tags=["status"], dependencies=_auth)
api_router.include_router(search_router, prefix="/embed", tags=["search"], dependencies=_auth)
api_router.include_router(documents_router, prefix="/document", tags=["documents"], dependencies=_auth)
