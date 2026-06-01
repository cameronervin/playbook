"""Example CRUD endpoints.

Demonstrates the thin-route pattern: routes parse the request, call the
service, and return the response. No business logic or DB access here.
"""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, status

from app.auth.dependencies import AuthPrincipal, current_active_user
from app.schemas.example import ExampleCreate, ExampleResponse, ExampleUpdate
from app.services.example_service import ExampleService

router = APIRouter(prefix="/examples", tags=["Examples"])


@router.post("", status_code=status.HTTP_201_CREATED)
async def create_example(
    data: ExampleCreate,
    _user: Annotated[AuthPrincipal, Depends(current_active_user)],
    service: Annotated[ExampleService, Depends()],
) -> ExampleResponse:
    """Create a new example."""
    return await service.create(data)


@router.get("")
async def list_examples(
    _user: Annotated[AuthPrincipal, Depends(current_active_user)],
    service: Annotated[ExampleService, Depends()],
    status: str | None = None,
) -> list[ExampleResponse]:
    """List examples, optionally filtered by status."""
    return await service.list(status=status)


@router.get("/{example_id}")
async def get_example(
    example_id: UUID,
    _user: Annotated[AuthPrincipal, Depends(current_active_user)],
    service: Annotated[ExampleService, Depends()],
) -> ExampleResponse:
    """Get a single example by id."""
    return await service.get(example_id)


@router.patch("/{example_id}")
async def update_example(
    example_id: UUID,
    data: ExampleUpdate,
    _user: Annotated[AuthPrincipal, Depends(current_active_user)],
    service: Annotated[ExampleService, Depends()],
) -> ExampleResponse:
    """Update an example."""
    return await service.update(example_id, data)


@router.delete("/{example_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_example(
    example_id: UUID,
    _user: Annotated[AuthPrincipal, Depends(current_active_user)],
    service: Annotated[ExampleService, Depends()],
) -> None:
    """Delete an example."""
    await service.delete(example_id)
