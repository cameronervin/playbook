from __future__ import annotations

from datetime import UTC, datetime
from types import SimpleNamespace
from uuid import uuid4

import pytest

from app.schemas.search import SearchRequest
from app.services.configuration_service import (
    DEFAULT_COLLECTION_NAME,
    DEFAULT_CONFIGURATION_NAME,
)
from app.services.search_service import SearchService


class FakeConfigurationService:
    def __init__(self) -> None:
        self.resolve_calls = 0
        now = datetime.now(UTC)
        self.config = SimpleNamespace(
            id=uuid4(),
            name=DEFAULT_CONFIGURATION_NAME,
            collection_name=DEFAULT_COLLECTION_NAME,
            version=1,
            parse_config={},
            chunk_config={},
            embed_config={},
            vectorstore_config={},
            created_at=now,
            updated_at=now,
        )

    async def resolve(self, data=None) -> SimpleNamespace:
        self.resolve_calls += 1
        return self.config


class FakeEmbedProvider:
    def __init__(self, vectors: list[list[float]]) -> None:
        self.vectors = vectors
        self.requests: list[list[str]] = []

    def embed(self, texts: list[str]) -> list[list[float]]:
        self.requests.append(texts)
        return self.vectors


class FakeVectorRepository:
    def __init__(self) -> None:
        self.requests: list[dict] = []

    async def search(self, **kwargs) -> list[dict]:
        self.requests.append(kwargs)
        return []


@pytest.mark.asyncio
async def test_search_resolves_default_configuration_before_vector_search() -> None:
    config_service = FakeConfigurationService()
    vector_repo = FakeVectorRepository()
    embed_provider = FakeEmbedProvider([[0.1, 0.2, 0.3]])
    service = SearchService(
        configuration_service=config_service,  # type: ignore[arg-type]
        vector_repo=vector_repo,  # type: ignore[arg-type]
        embed_provider=embed_provider,  # type: ignore[arg-type]
    )
    organization_id = uuid4()

    response = await service.search(
        SearchRequest(
            query="nil disclosure",
            organization_id=organization_id,
            visibility_context={"role": "athlete"},
        )
    )

    assert response.total == 0
    assert config_service.resolve_calls == 1
    assert vector_repo.requests[0]["configuration_id"] == config_service.config.id
    assert vector_repo.requests[0]["metadata_filters"] == [
        {
            "source_type": "admin_upload",
            "visibility_policy": {"scope": "all_athletes"},
        }
    ]


@pytest.mark.asyncio
async def test_search_returns_zero_results_for_fresh_default_without_vectors() -> None:
    config_service = FakeConfigurationService()
    vector_repo = FakeVectorRepository()
    embed_provider = FakeEmbedProvider([])
    service = SearchService(
        configuration_service=config_service,  # type: ignore[arg-type]
        vector_repo=vector_repo,  # type: ignore[arg-type]
        embed_provider=embed_provider,  # type: ignore[arg-type]
    )

    response = await service.search(
        SearchRequest(query="compliance", organization_id=uuid4())
    )

    assert response.results == []
    assert response.total == 0
    assert config_service.resolve_calls == 1
    assert vector_repo.requests == []


@pytest.mark.asyncio
async def test_search_builds_private_conversation_file_filter() -> None:
    config_service = FakeConfigurationService()
    vector_repo = FakeVectorRepository()
    embed_provider = FakeEmbedProvider([[0.1, 0.2, 0.3]])
    service = SearchService(
        configuration_service=config_service,  # type: ignore[arg-type]
        vector_repo=vector_repo,  # type: ignore[arg-type]
        embed_provider=embed_provider,  # type: ignore[arg-type]
    )
    conversation_id = uuid4()

    await service.search(
        SearchRequest(
            query="contract approval",
            organization_id=uuid4(),
            source_types=["conversation_file"],
            conversation_id=conversation_id,
        )
    )

    assert vector_repo.requests[0]["metadata_filters"] == [
        {
            "source_type": "conversation_file",
            "conversation_id": str(conversation_id),
            "visibility_policy": {"scope": "conversation"},
        }
    ]


@pytest.mark.asyncio
async def test_search_builds_file_narrowed_private_filters() -> None:
    config_service = FakeConfigurationService()
    vector_repo = FakeVectorRepository()
    embed_provider = FakeEmbedProvider([[0.1, 0.2, 0.3]])
    service = SearchService(
        configuration_service=config_service,  # type: ignore[arg-type]
        vector_repo=vector_repo,  # type: ignore[arg-type]
        embed_provider=embed_provider,  # type: ignore[arg-type]
    )
    conversation_id = uuid4()
    file_a = uuid4()
    file_b = uuid4()

    await service.search(
        SearchRequest(
            query="contract approval",
            organization_id=uuid4(),
            source_types=["conversation_file"],
            conversation_id=conversation_id,
            file_ids=[file_a, file_b],
        )
    )

    assert vector_repo.requests[0]["metadata_filters"] == [
        {
            "source_type": "conversation_file",
            "conversation_id": str(conversation_id),
            "conversation_file_id": str(file_a),
            "visibility_policy": {"scope": "conversation"},
        },
        {
            "source_type": "conversation_file",
            "conversation_id": str(conversation_id),
            "conversation_file_id": str(file_b),
            "visibility_policy": {"scope": "conversation"},
        },
    ]


@pytest.mark.asyncio
async def test_search_builds_combined_shared_and_private_filters() -> None:
    config_service = FakeConfigurationService()
    vector_repo = FakeVectorRepository()
    embed_provider = FakeEmbedProvider([[0.1, 0.2, 0.3]])
    service = SearchService(
        configuration_service=config_service,  # type: ignore[arg-type]
        vector_repo=vector_repo,  # type: ignore[arg-type]
        embed_provider=embed_provider,  # type: ignore[arg-type]
    )
    conversation_id = uuid4()

    await service.search(
        SearchRequest(
            query="nil contract approval",
            organization_id=uuid4(),
            source_types=["admin_upload", "conversation_file"],
            conversation_id=conversation_id,
            visibility_context={"role": "athlete"},
        )
    )

    assert vector_repo.requests[0]["metadata_filters"] == [
        {
            "source_type": "admin_upload",
            "visibility_policy": {"scope": "all_athletes"},
        },
        {
            "source_type": "conversation_file",
            "conversation_id": str(conversation_id),
            "visibility_policy": {"scope": "conversation"},
        },
    ]
