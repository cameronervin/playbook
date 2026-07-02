"""Tests for backend liveness and readiness routes."""

from __future__ import annotations

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.v1 import health as health_module
from app.core.config import Settings
from app.main import API_V1_PREFIX


def _test_app(settings: Settings) -> FastAPI:
    app = FastAPI()
    app.state.settings = settings
    app.include_router(health_module.router, prefix=API_V1_PREFIX)
    return app


def test_health_route_stays_liveness_probe(test_settings) -> None:
    app = _test_app(test_settings)

    with TestClient(app) as client:
        response = client.get("/api/v1/health")

    assert response.status_code == 200
    assert response.json() == {"status": "healthy"}


def test_ready_route_returns_503_when_dependency_degraded(monkeypatch, test_settings) -> None:
    async def degraded_database(settings) -> tuple[str, str]:
        return "postgres", "error: unavailable"

    async def ok_kb_provider(request, settings) -> tuple[str, str]:
        return "knowledgebase", "ok"

    monkeypatch.setattr(health_module, "_check_database", degraded_database)
    monkeypatch.setattr(health_module, "_check_kb_provider", ok_kb_provider)
    app = _test_app(test_settings)

    with TestClient(app) as client:
        response = client.get("/api/v1/ready")

    assert response.status_code == 503
    assert response.json()["status"] == "degraded"
    assert response.json()["checks"]["postgres"] == "error: unavailable"
