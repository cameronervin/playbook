"""Business logic for the Example entity.

Services hold the business logic, orchestrate repositories, raise domain
errors, and return DTOs (never raw ORM models). Dependencies are injected via
FastAPI `Depends()`.
"""

from uuid import UUID

import structlog
from fastapi import Depends

from app.core.exceptions import NotFoundError
from app.repositories.example_repository import ExampleRepository
from app.schemas.example import ExampleCreate, ExampleResponse, ExampleUpdate

logger = structlog.get_logger(__name__)


class ExampleService:
    """Orchestrates Example CRUD operations."""

    def __init__(self, repo: ExampleRepository = Depends()) -> None:
        self.repo = repo

    async def create(self, data: ExampleCreate) -> ExampleResponse:
        example = await self.repo.create(data.model_dump())
        logger.info("example_created", example_id=str(example.id), status=example.status)
        return ExampleResponse.model_validate(example)

    async def get(self, example_id: UUID) -> ExampleResponse:
        example = await self.repo.get(example_id)
        if example is None:
            raise NotFoundError("Example", str(example_id))
        return ExampleResponse.model_validate(example)

    async def list(self, status: str | None = None) -> list[ExampleResponse]:
        examples = await self.repo.list(status=status)
        return [ExampleResponse.model_validate(e) for e in examples]

    async def update(self, example_id: UUID, data: ExampleUpdate) -> ExampleResponse:
        payload = data.model_dump(exclude_unset=True)
        example = await self.repo.update(example_id, payload)
        if example is None:
            raise NotFoundError("Example", str(example_id))
        logger.info("example_updated", example_id=str(example_id))
        return ExampleResponse.model_validate(example)

    async def delete(self, example_id: UUID) -> None:
        deleted = await self.repo.delete(example_id)
        if not deleted:
            raise NotFoundError("Example", str(example_id))
        logger.info("example_deleted", example_id=str(example_id))
