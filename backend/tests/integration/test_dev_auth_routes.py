"""Route-level tests for local-development auth bootstrap endpoints."""

from __future__ import annotations

from collections.abc import AsyncGenerator

import jwt
import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession
from structlog.testing import capture_logs

from app.core.config import Settings
from app.infrastructure.db.session import get_db
from app.main import create_app

CUSTOM_ACCESS_COOKIE_NAME = "playbook_dev_session"


async def _client_for_app(app: FastAPI) -> AsyncGenerator[AsyncClient, None]:
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        yield client


async def _dev_auth_client(
    db_session: AsyncSession,
    settings: Settings,
) -> AsyncGenerator[AsyncClient, None]:
    app = create_app(app_settings=settings)

    async def override_get_db() -> AsyncGenerator[AsyncSession, None]:
        yield db_session

    app.dependency_overrides[get_db] = override_get_db
    async for client in _client_for_app(app):
        yield client
    app.dependency_overrides = {}


@pytest.mark.asyncio
async def test_dev_session_route_is_absent_when_disabled(
    db_session,
    monkeypatch,
    test_settings,
) -> None:
    monkeypatch.setattr(test_settings, "DEV_AUTH_ENABLED", False)

    async for client in _dev_auth_client(db_session, test_settings):
        response = await client.get(
            "/api/v1/dev/session/athlete",
            follow_redirects=False,
        )

    assert response.status_code == 404


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("persona", "next_route"),
    [
        ("athlete", "/chat"),
        ("new_athlete", "/profile"),
        ("admin", "/admin"),
        ("super_admin", "/admin"),
    ],
)
async def test_dev_session_redirects_and_sets_cookie_for_persona(
    db_session,
    monkeypatch,
    test_settings,
    persona,
    next_route,
) -> None:
    monkeypatch.setattr(test_settings, "DEV_AUTH_ENABLED", True)
    monkeypatch.setattr(test_settings, "ENVIRONMENT", "local")
    monkeypatch.setattr(test_settings, "DEBUG", True)
    monkeypatch.setattr(test_settings, "FRONTEND_URL", "http://localhost:3000")
    monkeypatch.setattr(test_settings, "COOKIE_DOMAIN", "")
    monkeypatch.setattr(test_settings, "ACCESS_TOKEN_COOKIE_NAME", CUSTOM_ACCESS_COOKIE_NAME)

    async for client in _dev_auth_client(db_session, test_settings):
        response = await client.get(
            f"/api/v1/dev/session/{persona}",
            follow_redirects=False,
        )

        me_response = await client.get("/api/v1/users/me")

    assert response.status_code == 303
    assert response.headers["location"] == f"http://localhost:3000{next_route}"
    assert f"{CUSTOM_ACCESS_COOKIE_NAME}=" in response.headers["set-cookie"]
    assert me_response.status_code == 200
    assert me_response.json()["role"] == ("super_admin" if persona == "super_admin" else persona if persona in {"admin", "athlete"} else "athlete")
    assert me_response.json()["profile_complete"] is (persona != "new_athlete")

    token = response.cookies.get(CUSTOM_ACCESS_COOKIE_NAME)
    assert token is not None
    payload = jwt.decode(token, test_settings.SECRET_KEY, algorithms=["HS256"])
    assert payload["sub"] == me_response.json()["id"]


@pytest.mark.asyncio
async def test_dev_session_rejects_invalid_persona(
    db_session,
    monkeypatch,
    test_settings,
) -> None:
    monkeypatch.setattr(test_settings, "DEV_AUTH_ENABLED", True)
    monkeypatch.setattr(test_settings, "ENVIRONMENT", "local")
    monkeypatch.setattr(test_settings, "DEBUG", True)
    monkeypatch.setattr(test_settings, "COOKIE_DOMAIN", "")

    async for client in _dev_auth_client(db_session, test_settings):
        response = await client.get(
            "/api/v1/dev/session/operator",
            follow_redirects=False,
        )

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "VALIDATION_ERROR"


@pytest.mark.asyncio
async def test_dev_session_logs_no_tokens_or_seed_emails(
    db_session,
    monkeypatch,
    test_settings,
) -> None:
    monkeypatch.setattr(test_settings, "DEV_AUTH_ENABLED", True)
    monkeypatch.setattr(test_settings, "ENVIRONMENT", "local")
    monkeypatch.setattr(test_settings, "DEBUG", True)
    monkeypatch.setattr(test_settings, "FRONTEND_URL", "http://localhost:3000")
    monkeypatch.setattr(test_settings, "COOKIE_DOMAIN", "")
    monkeypatch.setattr(test_settings, "ACCESS_TOKEN_COOKIE_NAME", CUSTOM_ACCESS_COOKIE_NAME)

    async for client in _dev_auth_client(db_session, test_settings):
        with capture_logs() as captured_logs:
            response = await client.get(
                "/api/v1/dev/session/admin",
                follow_redirects=False,
            )

    assert response.status_code == 303
    token = response.cookies.get(CUSTOM_ACCESS_COOKIE_NAME)
    assert token is not None
    log_blob = " ".join(str(entry) for entry in captured_logs)
    assert "phase1-admin@example.com" not in log_blob
    assert "phase1-athlete@example.com" not in log_blob
    assert "phase1-new-athlete@example.com" not in log_blob
    assert token not in log_blob
