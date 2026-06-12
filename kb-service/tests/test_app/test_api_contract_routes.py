from __future__ import annotations

from datetime import UTC, datetime
from uuid import uuid4

from fastapi.testclient import TestClient

from app.api.deps.services import get_configuration_service
from app.main import app


class FakeConfigurationService:
    def __init__(self) -> None:
        self.requests = []

    async def resolve(self, body=None):
        self.requests.append(body)
        now = datetime.now(UTC)
        return {
            "id": uuid4(),
            "name": "Playbook KB Pipeline",
            "collection_name": "playbook-kb",
            "version": 1,
            "parse_config": {"strategy": "auto"},
            "chunk_config": {},
            "embed_config": {},
            "vectorstore_config": {},
            "created_at": now.isoformat(),
            "updated_at": now.isoformat(),
        }


def test_openapi_exposes_only_canonical_kb_contract_routes() -> None:
    client = TestClient(app)

    response = client.get("/openapi.json")

    assert response.status_code == 200
    paths = set(response.json()["paths"])
    assert {
        "/api/kb/configuration/resolve",
        "/api/kb/ingest/document",
        "/api/kb/search",
        "/api/kb/status/documents/{document_id}",
        "/api/kb/documents/{document_id}/retry",
        "/api/kb/documents/{document_id}",
    }.issubset(paths)
    assert "/api/kb/embed/search" not in paths
    assert "/api/kb/ingest/url" not in paths
    assert "/api/kb/configuration/" not in paths
    assert "/api/kb/document/{document_id}" not in paths
    assert "/api/kb/status/{task_id}" not in paths


def test_legacy_scaffold_routes_return_404() -> None:
    client = TestClient(app)
    document_id = uuid4()

    assert client.post("/api/kb/embed/search", json={}).status_code == 404
    assert client.post("/api/kb/ingest/url", json={}).status_code == 404
    assert client.get("/api/kb/configuration/").status_code == 404
    assert client.delete(f"/api/kb/document/{document_id}").status_code == 404
    assert client.get(f"/api/kb/status/{document_id}").status_code == 404


def test_canonical_kb_routes_require_service_auth() -> None:
    client = TestClient(app)
    document_id = uuid4()

    assert client.post("/api/kb/configuration/resolve", json={}).status_code == 401
    assert client.post("/api/kb/ingest/document", json={}).status_code == 401
    assert client.post("/api/kb/search", json={}).status_code == 401
    assert client.get(f"/api/kb/status/documents/{document_id}").status_code == 401
    assert client.post(f"/api/kb/documents/{document_id}/retry").status_code == 401
    assert client.delete(f"/api/kb/documents/{document_id}").status_code == 401


def test_configuration_resolve_accepts_empty_authenticated_request() -> None:
    client = TestClient(app)
    fake_service = FakeConfigurationService()
    app.dependency_overrides[get_configuration_service] = lambda: fake_service
    try:
        response = client.post(
            "/api/kb/configuration/resolve",
            json={},
            headers={"Authorization": "Bearer test-api-secret"},
        )
    finally:
        app.dependency_overrides = {}

    assert response.status_code == 200
    assert response.json()["name"] == "Playbook KB Pipeline"
    assert response.json()["collection_name"] == "playbook-kb"
