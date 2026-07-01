"""Admin KB collection and metadata tag routes."""

from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Query, status
from fastapi.responses import Response

from app.api.v1.dependencies import (
    AdminUserDep,
    KBCatalogServiceDep,
    SuperAdminUserDep,
)
from app.schemas.kb_documents import (
    KBCollectionCreateRequest,
    KBCollectionResponse,
    KBMetadataTagCreateRequest,
    KBMetadataTagResponse,
    KBMetadataTagUpdateRequest,
)

router = APIRouter(prefix="/admin/kb", tags=["KB Catalog"])


@router.get("/collections", response_model=list[KBCollectionResponse])
async def list_collections(
    actor: AdminUserDep,
    service: KBCatalogServiceDep,
) -> list[KBCollectionResponse]:
    """List organization KB collections."""
    return await service.list_collections(actor=actor)


@router.post(
    "/collections",
    response_model=KBCollectionResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_collection(
    request: KBCollectionCreateRequest,
    actor: SuperAdminUserDep,
    service: KBCatalogServiceDep,
) -> KBCollectionResponse:
    """Create an organization KB collection."""
    return await service.create_collection(actor=actor, request=request)


@router.delete("/collections/{collection_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_collection(
    collection_id: UUID,
    actor: SuperAdminUserDep,
    service: KBCatalogServiceDep,
) -> Response:
    """Archive an empty organization KB collection."""
    await service.delete_collection(actor=actor, collection_id=collection_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/metadata-tags", response_model=list[KBMetadataTagResponse])
async def list_metadata_tags(
    actor: AdminUserDep,
    service: KBCatalogServiceDep,
    include_archived: Annotated[bool, Query()] = False,
) -> list[KBMetadataTagResponse]:
    """List global organization metadata tag presets."""
    return await service.list_tags(actor=actor, include_archived=include_archived)


@router.post(
    "/metadata-tags",
    response_model=KBMetadataTagResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_metadata_tag(
    request: KBMetadataTagCreateRequest,
    actor: SuperAdminUserDep,
    service: KBCatalogServiceDep,
) -> KBMetadataTagResponse:
    """Create a global organization metadata tag preset."""
    return await service.create_tag(actor=actor, request=request)


@router.patch("/metadata-tags/{tag_id}", response_model=KBMetadataTagResponse)
async def update_metadata_tag(
    tag_id: UUID,
    request: KBMetadataTagUpdateRequest,
    actor: SuperAdminUserDep,
    service: KBCatalogServiceDep,
) -> KBMetadataTagResponse:
    """Update a metadata tag preset label."""
    return await service.update_tag(actor=actor, tag_id=tag_id, request=request)


@router.post("/metadata-tags/{tag_id}/unarchive", response_model=KBMetadataTagResponse)
async def unarchive_metadata_tag(
    tag_id: UUID,
    actor: SuperAdminUserDep,
    service: KBCatalogServiceDep,
) -> KBMetadataTagResponse:
    """Restore an archived metadata tag preset."""
    return await service.unarchive_tag(actor=actor, tag_id=tag_id)


@router.delete(
    "/metadata-tags/{tag_id}/permanent",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def permanently_delete_metadata_tag(
    tag_id: UUID,
    actor: SuperAdminUserDep,
    service: KBCatalogServiceDep,
) -> Response:
    """Permanently delete an unused archived metadata tag preset."""
    await service.permanently_delete_tag(actor=actor, tag_id=tag_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.delete("/metadata-tags/{tag_id}", status_code=status.HTTP_204_NO_CONTENT)
async def archive_metadata_tag(
    tag_id: UUID,
    actor: SuperAdminUserDep,
    service: KBCatalogServiceDep,
) -> Response:
    """Archive a metadata tag preset."""
    await service.archive_tag(actor=actor, tag_id=tag_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
