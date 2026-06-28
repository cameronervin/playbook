"""Regression tests for explicit backend settings injection."""

from __future__ import annotations

from collections.abc import AsyncGenerator
from datetime import UTC, datetime, timedelta
from pathlib import Path
from uuid import uuid4

import jwt
import pytest
from httpx import ASGITransport, AsyncClient

from app.core.config import Settings
from app.infrastructure.db.session import get_db
from app.main import create_app
from app.models.identity import User
from app.repositories.identity import AppSessionRepository, OrganizationRepository, UserRepository


APP_ROOT = Path(__file__).resolve().parents[2] / "app"


def _settings(**overrides: object) -> Settings:
    values: dict[str, object] = {
        "DATABASE_URL": "postgresql+asyncpg://app:pass@localhost:5432/playbook",
        "SECRET_KEY": "test-secret-value-that-is-long-enough",
        "OAUTH_STATE_SECRET": "test-oauth-secret-value-that-is-long-enough",
        "LLM_PROVIDER_MODE": "direct",
        "LLM_DIRECT_PROVIDER": "anthropic",
        "ANTHROPIC_API_KEY": "anthropic-key",
        "ENVIRONMENT": "test",
        "DEBUG": False,
        "DEV_AUTH_ENABLED": False,
    }
    values.update(overrides)
    return Settings(_env_file=None, **values)


def test_create_app_never_mounts_legacy_dev_session_route() -> None:
    disabled_app = create_app(app_settings=_settings(DEV_AUTH_ENABLED=False))
    enabled_app = create_app(
        app_settings=_settings(
            ENVIRONMENT="local",
            DEBUG=True,
            DEV_AUTH_ENABLED=True,
        )
    )

    disabled_paths = {route.path for route in disabled_app.routes}
    enabled_paths = {route.path for route in enabled_app.routes}

    assert "/api/v1/dev/session/{persona}" not in disabled_paths
    assert "/api/v1/dev/session/{persona}" not in enabled_paths
    assert "/api/v1/auth/{provider}/login" in enabled_paths


@pytest.mark.asyncio
async def test_auth_dependency_uses_injected_cookie_and_secret(db_session) -> None:
    settings = _settings(
        ACCESS_TOKEN_COOKIE_NAME="custom_access",
        SECRET_KEY="custom-test-secret-value-that-is-long-enough",
    )
    app = create_app(app_settings=settings)

    async def override_get_db() -> AsyncGenerator:
        yield db_session

    app.dependency_overrides[get_db] = override_get_db
    organization = await OrganizationRepository(db_session).create(
        name="Playbook Athletics",
        slug=f"settings-injection-{uuid4()}",
    )
    user = await UserRepository(db_session).create(
        organization_id=organization.id,
        email="settings-injected@example.com",
        name="Injected Settings",
        auth_provider="google",
        provider_subject="settings-injected",
        role="athlete",
        sport_team="Basketball",
    )
    app_session = await AppSessionRepository(db_session).create(
        user_id=user.id,
        expires_at=datetime.now(UTC) + timedelta(hours=1),
    )
    token = jwt.encode(
        {
            "sub": str(user.id),
            "sid": str(app_session.id),
            "role": user.role,
            "iat": int(datetime.now(UTC).timestamp()),
            "exp": int(app_session.expires_at.timestamp()),
        },
        settings.SECRET_KEY,
        algorithm="HS256",
    )

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        response = await client.get(
            "/api/v1/users/me",
            cookies={settings.ACCESS_TOKEN_COOKIE_NAME: token},
        )

    assert response.status_code == 200
    assert response.json()["id"] == str(user.id)


def test_backend_app_modules_do_not_import_settings_singleton() -> None:
    offenders: list[str] = []
    for path in APP_ROOT.rglob("*.py"):
        if path.name == "config.py":
            continue
        text = path.read_text()
        if "from app.core.config import settings" in text:
            offenders.append(str(path.relative_to(APP_ROOT.parent)))

    assert offenders == []
