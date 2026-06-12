"""Configuration contract endpoints. Routes stay thin — logic in service."""
from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status

from app.api.deps.services import get_configuration_service
from app.schemas.configuration import (
    ConfigurationResolveRequest,
    ConfigurationResponse,
)
from app.services.configuration_service import (
    ConfigurationConflictError,
    ConfigurationService,
)

router = APIRouter()


@router.post("/resolve", response_model=ConfigurationResponse)
async def resolve_configuration(
    svc: Annotated[ConfigurationService, Depends(get_configuration_service)],
    body: ConfigurationResolveRequest | None = None,
) -> ConfigurationResponse:
    """Resolve or create the default Playbook KB configuration."""
    try:
        return await svc.resolve(body)
    except ConfigurationConflictError:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Default KB configuration conflicts with existing database state",
        ) from None
