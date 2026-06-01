"""Unit tests for ExampleService.

Demonstrates the testing pattern: the repository is mocked (AsyncMock) so the
service's business logic is exercised in isolation, no database required.
"""
from uuid import uuid4

import pytest
from unittest.mock import AsyncMock

from app.core.exceptions import NotFoundError
from app.models.example import Example
from app.schemas.example import ExampleCreate, ExampleResponse, ExampleUpdate
from app.services.example_service import ExampleService


def _make_example(**kwargs) -> Example:
    """Build a transient Example ORM instance for from_attributes serialization."""
    from datetime import UTC, datetime

    example = Example()
    example.id = kwargs.get("id", uuid4())
    example.name = kwargs.get("name", "Test")
    example.status = kwargs.get("status", "active")
    example.created_at = kwargs.get("created_at", datetime.now(UTC))
    return example


@pytest.fixture
def repo() -> AsyncMock:
    return AsyncMock()


@pytest.fixture
def service(repo: AsyncMock) -> ExampleService:
    return ExampleService(repo=repo)


@pytest.mark.asyncio
async def test_create_returns_response_dto(service: ExampleService, repo: AsyncMock):
    created = _make_example(name="Gadget", status="active")
    repo.create.return_value = created

    result = await service.create(ExampleCreate(name="Gadget"))

    assert isinstance(result, ExampleResponse)
    assert result.name == "Gadget"
    assert result.status == "active"
    repo.create.assert_awaited_once()


@pytest.mark.asyncio
async def test_get_missing_raises_not_found(service: ExampleService, repo: AsyncMock):
    repo.get.return_value = None

    with pytest.raises(NotFoundError):
        await service.get(uuid4())


@pytest.mark.asyncio
async def test_update_only_sends_set_fields(service: ExampleService, repo: AsyncMock):
    example_id = uuid4()
    repo.update.return_value = _make_example(id=example_id, name="Updated", status="archived")

    result = await service.update(example_id, ExampleUpdate(status="archived"))

    assert result.status == "archived"
    # exclude_unset means only 'status' is forwarded to the repository.
    _, payload = repo.update.await_args.args
    assert payload == {"status": "archived"}


@pytest.mark.asyncio
async def test_delete_missing_raises_not_found(service: ExampleService, repo: AsyncMock):
    repo.delete.return_value = False

    with pytest.raises(NotFoundError):
        await service.delete(uuid4())
