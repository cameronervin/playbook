from __future__ import annotations

from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

from fastapi.testclient import TestClient

from app.api import health as health_module
from app.api.deps.services import get_configuration_service, get_ingestion_service
from app.core.config import Settings
from app.main import app, cors_origins_for_settings, docs_urls_for_settings
from app.schemas.ingest import (
    DocumentMetadataRefreshResponse,
    IngestDocumentResponse,
)


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


class FakeIngestionService:
    def __init__(self) -> None:
        self.requests: list[Any] = []

    async def start_ingest(self, body: Any) -> IngestDocumentResponse:
        self.requests.append(body)
        return IngestDocumentResponse(
            kb_service_document_id=uuid4(),
            source_type=body.source_type,
            playbook_document_id=getattr(body, "playbook_document_id", None),
            conversation_id=getattr(body, "conversation_id", None),
            conversation_file_id=getattr(body, "conversation_file_id", None),
            task_id="fake-task-id",
            status="pending",
        )

    async def refresh_document_metadata(
        self,
        document_id,
        body: Any,
    ) -> DocumentMetadataRefreshResponse:
        self.requests.append((document_id, body))
        return DocumentMetadataRefreshResponse(
            kb_service_document_id=document_id,
            source_type="admin_upload",
            playbook_document_id=uuid4(),
            updated_embedding_count=3,
            metadata={"source_date": "2026-02-01"},
        )


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
        "/api/kb/documents/{document_id}/metadata",
        "/api/kb/documents/{document_id}",
    }.issubset(paths)
    assert "/api/kb/embed/search" not in paths
    assert "/api/kb/ingest/url" not in paths
    assert "/api/kb/configuration/" not in paths
    assert "/api/kb/document/{document_id}" not in paths
    assert "/api/kb/status/{task_id}" not in paths


def test_search_openapi_keeps_ranking_fields_in_result_metadata() -> None:
    client = TestClient(app)

    response = client.get("/openapi.json")

    assert response.status_code == 200
    schemas = response.json()["components"]["schemas"]
    result_props = schemas["SearchResult"]["properties"]
    request_props = schemas["SearchRequest"]["properties"]

    assert "score" in result_props
    assert "metadata" in result_props
    assert "semantic_score" not in result_props
    assert "semantic_rank" not in result_props
    assert "lexical_score" not in result_props
    assert "lexical_rank" not in result_props
    assert "hybrid_score" not in result_props
    assert "rerank_score" not in result_props
    assert "ranking_strategy" not in result_props
    assert "admin_upload" in request_props["source_types"]["description"]
    assert "conversation_file" in request_props["source_types"]["description"]


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
    assert client.patch(f"/api/kb/documents/{document_id}/metadata").status_code == 401
    assert client.delete(f"/api/kb/documents/{document_id}").status_code == 401


def test_canonical_kb_routes_reject_bad_bearer_token() -> None:
    client = TestClient(app)

    response = client.post(
        "/api/kb/configuration/resolve",
        json={},
        headers={"Authorization": "Bearer wrong-secret"},
    )

    assert response.status_code == 401


def test_health_routes_allow_unauthenticated_access(monkeypatch) -> None:
    async def ok_postgres() -> tuple[str, str]:
        return "postgres", "ok"

    async def ok_valkey() -> tuple[str, str]:
        return "valkey", "ok"

    monkeypatch.setattr(health_module, "_check_postgres", ok_postgres)
    monkeypatch.setattr(health_module, "_check_valkey", ok_valkey)
    client = TestClient(app)

    assert client.get("/health").status_code == 200
    assert client.get("/api/kb/health").status_code == 200


def test_health_routes_return_503_when_dependencies_are_degraded(monkeypatch) -> None:
    async def degraded_postgres() -> tuple[str, str]:
        return "postgres", "error: unavailable"

    async def ok_valkey() -> tuple[str, str]:
        return "valkey", "ok"

    monkeypatch.setattr(health_module, "_check_postgres", degraded_postgres)
    monkeypatch.setattr(health_module, "_check_valkey", ok_valkey)
    client = TestClient(app)

    response = client.get("/api/kb/health")

    assert response.status_code == 503
    assert response.json()["status"] == "degraded"


def test_production_disables_docs_and_wildcard_cors() -> None:
    production_settings = Settings(
        _env_file=None,
        DATABASE_URL="postgresql+asyncpg://kb:kb@localhost:5432/kb",
        KB_WEBHOOK_SECRET="long-webhook-secret-value-123456",
        KB_API_SECRET="long-api-secret-value-1234567890",
        ENVIRONMENT="production",
        LLM_PROVIDER_MODE="litellm",
        LITELLM_BASE_URL="https://litellm.example.com",
        LITELLM_API_KEY="litellm-key",
        CORS_ORIGINS="https://app.example.com,https://admin.example.com",
    )

    assert docs_urls_for_settings(production_settings) == {
        "openapi_url": None,
        "docs_url": None,
        "redoc_url": None,
    }
    assert cors_origins_for_settings(production_settings) == [
        "https://app.example.com",
        "https://admin.example.com",
    ]


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


def test_ingest_route_accepts_conversation_file_without_playbook_document_id() -> None:
    client = TestClient(app)
    fake_service = FakeIngestionService()
    conversation_id = uuid4()
    conversation_file_id = uuid4()
    app.dependency_overrides[get_ingestion_service] = lambda: fake_service
    try:
        response = client.post(
            "/api/kb/ingest/document",
            json={
                "source_type": "conversation_file",
                "organization_id": str(uuid4()),
                "conversation_id": str(conversation_id),
                "conversation_file_id": str(conversation_file_id),
                "configuration_id": str(uuid4()),
                "source_uri": "s3://playbook-bucket/conversations/contract.pdf",
                "filename": "contract.pdf",
                "content_type": "application/pdf",
                "size_bytes": 100,
                "source_title": "Contract",
            },
            headers={"Authorization": "Bearer test-api-secret"},
        )
    finally:
        app.dependency_overrides = {}

    assert response.status_code == 202
    payload = response.json()
    assert payload["source_type"] == "conversation_file"
    assert payload["conversation_id"] == str(conversation_id)
    assert payload["conversation_file_id"] == str(conversation_file_id)
    assert payload["playbook_document_id"] is None


def test_document_metadata_refresh_route_accepts_authenticated_request() -> None:
    client = TestClient(app)
    fake_service = FakeIngestionService()
    document_id = uuid4()
    app.dependency_overrides[get_ingestion_service] = lambda: fake_service
    try:
        response = client.patch(
            f"/api/kb/documents/{document_id}/metadata",
            json={
                "source_date": "2026-02-01",
                "is_official": True,
                "priority": 0,
                "visibility_policy": {"scope": "all_athletes"},
                "metadata_tags": {"collection": "compliance"},
            },
            headers={"Authorization": "Bearer test-api-secret"},
        )
    finally:
        app.dependency_overrides = {}

    assert response.status_code == 200
    assert response.json()["kb_service_document_id"] == str(document_id)
    assert fake_service.requests[0][0] == document_id
    assert fake_service.requests[0][1].metadata_tags == {"collection": "compliance"}
