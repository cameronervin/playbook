from __future__ import annotations

from datetime import UTC, datetime
from types import SimpleNamespace
from uuid import uuid4

import pytest
from sqlalchemy.exc import IntegrityError

from app.services import configuration_service as configuration_module
from app.services.configuration_service import (
    DEFAULT_COLLECTION_NAME,
    DEFAULT_CONFIGURATION_NAME,
    ConfigurationConflictError,
    ConfigurationService,
)


def _config_row(
    *,
    name: str = DEFAULT_CONFIGURATION_NAME,
    collection_name: str = DEFAULT_COLLECTION_NAME,
) -> SimpleNamespace:
    now = datetime.now(UTC)
    return SimpleNamespace(
        id=uuid4(),
        name=name,
        collection_name=collection_name,
        version=1,
        parse_config={"strategy": "auto"},
        chunk_config={
            "strategy": "token_based_recursive",
            "chunk_size_tokens": 400,
            "chunk_overlap_tokens": 40,
            "tokenizer": "cl100k_base",
        },
        embed_config={"dimensions": 1536, "model": "playbook-embed"},
        vectorstore_config={"index_type": "hnsw", "m": 16, "ef_construction": 64},
        created_at=now,
        updated_at=now,
    )


class FakeSession:
    def __init__(self) -> None:
        self.rollback_count = 0

    async def rollback(self) -> None:
        self.rollback_count += 1


class FakeConfigurationRepository:
    def __init__(
        self,
        _session: FakeSession,
        *,
        existing: SimpleNamespace | None = None,
        create_error: Exception | None = None,
    ) -> None:
        self.existing = existing
        self.create_error = create_error
        self.created: list[object] = []
        self.get_by_name_calls: list[str] = []

    async def get_by_name(self, name: str) -> SimpleNamespace | None:
        self.get_by_name_calls.append(name)
        return self.existing

    async def get_by_collection_name(
        self,
        collection_name: str,
    ) -> SimpleNamespace | None:
        if self.existing and self.existing.collection_name == collection_name:
            return self.existing
        return None

    async def create(self, data: object) -> SimpleNamespace:
        self.created.append(data)
        if self.create_error is not None:
            raise self.create_error
        row = _config_row(
            name=data.name,
            collection_name=data.collection_name,
        )
        self.existing = row
        return row


def _service_with_repo(
    monkeypatch: pytest.MonkeyPatch,
    repo: FakeConfigurationRepository,
    session: FakeSession,
) -> ConfigurationService:
    monkeypatch.setattr(
        configuration_module,
        "ConfigurationRepository",
        lambda _session: repo,
    )
    return ConfigurationService(session)  # type: ignore[arg-type]


@pytest.mark.asyncio
async def test_resolve_creates_default_configuration(monkeypatch: pytest.MonkeyPatch) -> None:
    session = FakeSession()
    repo = FakeConfigurationRepository(session)
    service = _service_with_repo(monkeypatch, repo, session)

    resolved = await service.resolve()

    assert resolved.name == DEFAULT_CONFIGURATION_NAME
    assert resolved.collection_name == DEFAULT_COLLECTION_NAME
    assert len(repo.created) == 1


@pytest.mark.asyncio
async def test_resolve_returns_existing_default_configuration(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    session = FakeSession()
    existing = _config_row()
    repo = FakeConfigurationRepository(session, existing=existing)
    service = _service_with_repo(monkeypatch, repo, session)

    first = await service.resolve()
    second = await service.resolve()

    assert first.id == existing.id
    assert second.id == existing.id
    assert repo.created == []


@pytest.mark.asyncio
async def test_resolve_recovers_from_concurrent_default_create(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    session = FakeSession()
    existing_after_conflict = _config_row()
    error = IntegrityError("insert", {}, Exception("duplicate key"))
    repo = FakeConfigurationRepository(session, create_error=error)
    service = _service_with_repo(monkeypatch, repo, session)

    original_get_by_name = repo.get_by_name

    async def get_by_name_after_conflict(name: str) -> SimpleNamespace | None:
        if len(repo.get_by_name_calls) == 0:
            return await original_get_by_name(name)
        repo.existing = existing_after_conflict
        return await original_get_by_name(name)

    repo.get_by_name = get_by_name_after_conflict  # type: ignore[method-assign]

    resolved = await service.resolve()

    assert resolved.id == existing_after_conflict.id
    assert session.rollback_count == 1


@pytest.mark.asyncio
async def test_resolve_reports_configuration_drift_after_integrity_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    session = FakeSession()
    drifted = _config_row(collection_name="other-collection")
    error = IntegrityError("insert", {}, Exception("duplicate key"))
    repo = FakeConfigurationRepository(session, create_error=error)
    service = _service_with_repo(monkeypatch, repo, session)

    async def get_by_name_after_conflict(name: str) -> SimpleNamespace | None:
        repo.get_by_name_calls.append(name)
        if len(repo.get_by_name_calls) == 1:
            return None
        return drifted

    repo.get_by_name = get_by_name_after_conflict  # type: ignore[method-assign]

    with pytest.raises(ConfigurationConflictError):
        await service.resolve()

    assert session.rollback_count == 1
