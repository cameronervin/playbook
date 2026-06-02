"""CRUD endpoints for /api/kb/configuration. Routes stay thin — logic in service."""
from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.exc import IntegrityError

from app.api.deps.services import get_configuration_service
from app.schemas.configuration import ConfigurationCreate, ConfigurationResponse
from app.services.configuration_service import ConfigurationService

router = APIRouter()


@router.post("", response_model=ConfigurationResponse, status_code=status.HTTP_201_CREATED)
async def create_configuration(
    body: ConfigurationCreate,
    svc: ConfigurationService = Depends(get_configuration_service),
) -> ConfigurationResponse:
    try:
        return await svc.create(body)
    except IntegrityError:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Configuration name already exists")


@router.get("/", response_model=list[ConfigurationResponse])
async def list_configurations(
    name: str | None = None,
    svc: ConfigurationService = Depends(get_configuration_service),
) -> list[ConfigurationResponse]:
    return await svc.list(name_filter=name)


@router.get("/{config_id}", response_model=ConfigurationResponse)
async def get_configuration(
    config_id: uuid.UUID,
    svc: ConfigurationService = Depends(get_configuration_service),
) -> ConfigurationResponse:
    config = await svc.get(config_id)
    if not config:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Configuration not found")
    return config


@router.delete("/{config_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_configuration(
    config_id: uuid.UUID,
    svc: ConfigurationService = Depends(get_configuration_service),
) -> None:
    await svc.delete(config_id)  # idempotent — no-op if not found
