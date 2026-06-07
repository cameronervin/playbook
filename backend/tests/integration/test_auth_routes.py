"""Route-level tests for Phase 1 authentication endpoints."""

from __future__ import annotations

from urllib.parse import urlencode

import jwt
import pytest
from httpx_oauth.oauth2 import OAuth2Error
from sqlalchemy import select
from structlog.processors import format_exc_info
from structlog.testing import capture_logs

from app.api.v1.dependencies import get_auth_service
from app.core.config import settings
from app.models.identity import OAuthAccount, User
from app.repositories.identity import OrganizationRepository, UserRepository
from app.services.auth_service import AuthService

CUSTOM_ACCESS_COOKIE_NAME = "playbook_session"
DEFAULT_ACCESS_COOKIE_NAME = "access_token"
TOKEN_EXPIRY = 999999


class FakeOAuthClient:
    """Tiny OAuth client fake matching the httpx-oauth methods we use."""

    def __init__(self, provider: str) -> None:
        self.provider = provider
        self.last_redirect_uri: str | None = None
        self.last_state: str | None = None
        self.fail_identity_lookup = False

    @property
    def access_token(self) -> str:
        return f"{self.provider}-provider-access-token"

    @property
    def refresh_token(self) -> str:
        return f"{self.provider}-provider-refresh-token"

    @property
    def subject(self) -> str:
        return f"{self.provider}-subject"

    @property
    def email(self) -> str:
        return f"{self.provider}@example.com"

    async def get_authorization_url(self, redirect_uri: str, *, state: str) -> str:
        self.last_redirect_uri = redirect_uri
        self.last_state = state
        query = urlencode({"redirect_uri": redirect_uri, "state": state})
        return f"https://oauth.example/{self.provider}/authorize?{query}"

    async def get_access_token(self, code: str, redirect_uri: str) -> dict[str, object]:
        self.last_redirect_uri = redirect_uri
        return {
            "access_token": self.access_token,
            "refresh_token": self.refresh_token,
            "expires_at": TOKEN_EXPIRY,
        }

    async def get_id_email(self, access_token: str) -> tuple[str, str]:
        if self.fail_identity_lookup:
            raise OAuth2Error(
                "provider identity failed "
                f"{self.access_token} {self.refresh_token}"
            )
        return self.subject, self.email


class FakeOAuthClientFactory:
    """Provider client factory that keeps fakes stable across requests."""

    def __init__(self) -> None:
        self.clients = {
            "google": FakeOAuthClient("google"),
            "microsoft": FakeOAuthClient("microsoft"),
        }

    def get_client(self, provider: str) -> FakeOAuthClient:
        return self.clients[provider]


def _configure_oauth_settings(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "COOKIE_DOMAIN", "")
    monkeypatch.setattr(settings, "GOOGLE_OAUTH_CLIENT_ID", "google-client")
    monkeypatch.setattr(settings, "GOOGLE_OAUTH_CLIENT_SECRET", "google-secret")
    monkeypatch.setattr(settings, "MICROSOFT_OAUTH_CLIENT_ID", "microsoft-client")
    monkeypatch.setattr(settings, "MICROSOFT_OAUTH_CLIENT_SECRET", "microsoft-secret")


def _override_auth_service(route_client, db_session, fake_factory) -> None:
    def override_auth_service() -> AuthService:
        return AuthService(db_session, client_factory=fake_factory)

    route_client.app.dependency_overrides[get_auth_service] = override_auth_service


def _log_blob(captured_logs: list[dict[str, object]]) -> str:
    return " ".join(str(entry) for entry in captured_logs)


@pytest.mark.asyncio
async def test_auth_provider_listing_uses_configured_providers(
    route_client,
    monkeypatch,
) -> None:
    monkeypatch.setattr(settings, "GOOGLE_OAUTH_CLIENT_ID", "google-client")
    monkeypatch.setattr(settings, "GOOGLE_OAUTH_CLIENT_SECRET", "google-secret")
    monkeypatch.setattr(settings, "MICROSOFT_OAUTH_CLIENT_ID", "microsoft-client")
    monkeypatch.setattr(settings, "MICROSOFT_OAUTH_CLIENT_SECRET", "microsoft-secret")

    response = await route_client.client.get("/api/v1/auth/providers")

    assert response.status_code == 200
    assert response.json() == {
        "providers": [
            {
                "provider": "google",
                "label": "Google",
                "enabled": True,
                "login_url": "/api/v1/auth/google/login",
            },
            {
                "provider": "microsoft",
                "label": "Microsoft",
                "enabled": True,
                "login_url": "/api/v1/auth/microsoft/login",
            },
        ]
    }


@pytest.mark.asyncio
@pytest.mark.parametrize("provider", ["google", "microsoft"])
async def test_oauth_callback_creates_session_without_exposing_provider_tokens(
    route_client,
    db_session,
    monkeypatch,
    provider,
) -> None:
    _configure_oauth_settings(monkeypatch)
    monkeypatch.setattr(settings, "ACCESS_TOKEN_COOKIE_NAME", CUSTOM_ACCESS_COOKIE_NAME)
    fake_factory = FakeOAuthClientFactory()
    _override_auth_service(route_client, db_session, fake_factory)

    login_response = await route_client.client.get(f"/api/v1/auth/{provider}/login")
    oauth_client = fake_factory.clients[provider]

    assert login_response.status_code == 200
    assert login_response.json()["authorization_url"].startswith(
        f"https://oauth.example/{provider}/authorize"
    )
    assert oauth_client.last_state is not None

    with capture_logs() as captured_logs:
        callback_response = await route_client.client.get(
            f"/api/v1/auth/{provider}/callback",
            params={"code": "oauth-code", "state": oauth_client.last_state},
        )

    assert callback_response.status_code == 200
    body = callback_response.json()
    assert body["user"]["email"] == oauth_client.email
    assert body["next_route"] == "/profile"
    assert body["access_token"] != oauth_client.access_token
    assert jwt.decode(body["access_token"], settings.SECRET_KEY, algorithms=["HS256"])[
        "sub"
    ]
    assert oauth_client.access_token not in callback_response.text
    assert oauth_client.refresh_token not in callback_response.text
    assert oauth_client.subject not in callback_response.text
    assert "access_token" in body
    assert "refresh_token" not in body
    assert "refresh_token" not in callback_response.text
    assert "oauth_accounts" not in body
    assert "oauth_accounts" not in callback_response.text
    assert "auth_provider" not in body["user"]
    assert "auth_provider" not in callback_response.text
    assert "provider_subject" not in body["user"]
    assert "provider_subject" not in callback_response.text

    set_cookie = callback_response.headers["set-cookie"]
    assert f"{CUSTOM_ACCESS_COOKIE_NAME}=" in set_cookie
    assert f"{DEFAULT_ACCESS_COOKIE_NAME}=" not in set_cookie
    assert oauth_client.access_token not in _log_blob(captured_logs)
    assert oauth_client.refresh_token not in _log_blob(captured_logs)

    account = await db_session.scalar(
        select(OAuthAccount).where(OAuthAccount.oauth_name == provider)
    )
    user = await db_session.scalar(select(User).where(User.email == oauth_client.email))
    assert account is not None
    assert user is not None
    assert account.user_id == user.id
    assert account.access_token == oauth_client.access_token
    assert account.refresh_token == oauth_client.refresh_token
    assert account.expires_at == TOKEN_EXPIRY
    assert user.auth_provider == provider
    assert user.provider_subject == oauth_client.subject


@pytest.mark.asyncio
async def test_oauth_callback_redirects_browser_callers_after_setting_cookie(
    route_client,
    db_session,
    monkeypatch,
) -> None:
    _configure_oauth_settings(monkeypatch)
    monkeypatch.setattr(settings, "FRONTEND_URL", "http://localhost:3000")
    monkeypatch.setattr(settings, "ACCESS_TOKEN_COOKIE_NAME", CUSTOM_ACCESS_COOKIE_NAME)
    fake_factory = FakeOAuthClientFactory()
    _override_auth_service(route_client, db_session, fake_factory)

    login_response = await route_client.client.get("/api/v1/auth/google/login")
    google_client = fake_factory.clients["google"]
    assert login_response.status_code == 200
    assert google_client.last_state is not None

    callback_response = await route_client.client.get(
        "/api/v1/auth/google/callback",
        params={"code": "oauth-code", "state": google_client.last_state},
        headers={"Accept": "text/html"},
        follow_redirects=False,
    )

    assert callback_response.status_code == 303
    assert callback_response.headers["location"] == "http://localhost:3000/profile"
    set_cookie = callback_response.headers["set-cookie"]
    assert f"{CUSTOM_ACCESS_COOKIE_NAME}=" in set_cookie
    assert f"{settings.OAUTH_STATE_COOKIE_NAME}=" in set_cookie
    assert "Max-Age=0" in set_cookie


@pytest.mark.asyncio
async def test_oauth_callback_failure_does_not_persist_or_log_provider_tokens(
    route_client,
    db_session,
    monkeypatch,
) -> None:
    _configure_oauth_settings(monkeypatch)
    monkeypatch.setattr(settings, "ACCESS_TOKEN_COOKIE_NAME", CUSTOM_ACCESS_COOKIE_NAME)
    fake_factory = FakeOAuthClientFactory()
    fake_factory.clients["google"].fail_identity_lookup = True
    _override_auth_service(route_client, db_session, fake_factory)

    login_response = await route_client.client.get("/api/v1/auth/google/login")
    google_client = fake_factory.clients["google"]
    assert login_response.status_code == 200
    assert google_client.last_state is not None

    with capture_logs(processors=[format_exc_info]) as captured_logs:
        callback_response = await route_client.client.get(
            "/api/v1/auth/google/callback",
            params={"code": "oauth-code", "state": google_client.last_state},
            headers={"X-Request-ID": "oauth-failure"},
        )

    assert callback_response.status_code == 502
    assert callback_response.json() == {
        "error": {
            "code": "OAUTH_ERROR",
            "message": "OAuth provider callback failed",
            "retryable": True,
            "details": {"provider": "google", "request_id": "oauth-failure"},
        }
    }
    assert CUSTOM_ACCESS_COOKIE_NAME not in callback_response.headers.get(
        "set-cookie", ""
    )
    assert google_client.access_token not in callback_response.text
    assert google_client.refresh_token not in callback_response.text
    assert google_client.access_token not in _log_blob(captured_logs)
    assert google_client.refresh_token not in _log_blob(captured_logs)
    assert await db_session.scalar(select(OAuthAccount)) is None
    assert await db_session.scalar(select(User).where(User.email == google_client.email)) is None


@pytest.mark.asyncio
@pytest.mark.parametrize("provider", ["google", "microsoft"])
async def test_oauth_login_supports_google_and_microsoft(
    route_client,
    db_session,
    monkeypatch,
    provider,
) -> None:
    _configure_oauth_settings(monkeypatch)
    fake_factory = FakeOAuthClientFactory()
    _override_auth_service(route_client, db_session, fake_factory)

    response = await route_client.client.get(f"/api/v1/auth/{provider}/login")

    assert response.status_code == 200
    assert f"https://oauth.example/{provider}/authorize" in response.json()[
        "authorization_url"
    ]


@pytest.mark.asyncio
async def test_logout_requires_authentication_and_clears_configured_cookie(
    route_client,
    db_session,
    monkeypatch,
) -> None:
    monkeypatch.setattr(settings, "COOKIE_DOMAIN", "")
    monkeypatch.setattr(settings, "ACCESS_TOKEN_COOKIE_NAME", CUSTOM_ACCESS_COOKIE_NAME)
    organization = await OrganizationRepository(db_session).create(
        name="Playbook Athletics",
        slug="playbook",
    )
    user = await UserRepository(db_session).create(
        organization_id=organization.id,
        email="athlete@example.com",
        name="Jordan Athlete",
        auth_provider="google",
        provider_subject="google-subject",
    )

    unauthenticated = await route_client.client.post("/api/v1/auth/logout")
    route_client.authenticate_as(user)
    route_client.client.cookies.set(CUSTOM_ACCESS_COOKIE_NAME, "session-token")
    authenticated = await route_client.client.post("/api/v1/auth/logout")

    assert unauthenticated.status_code == 401
    assert unauthenticated.json()["error"]["code"] == "UNAUTHORIZED"
    assert authenticated.status_code == 200
    assert authenticated.json() == {"status": "ok"}
    assert f"{CUSTOM_ACCESS_COOKIE_NAME}=" in authenticated.headers["set-cookie"]
    assert "Max-Age=0" in authenticated.headers["set-cookie"]


@pytest.mark.asyncio
async def test_current_user_dependency_accepts_configured_cookie_name(
    route_client,
    db_session,
    monkeypatch,
) -> None:
    monkeypatch.setattr(settings, "ACCESS_TOKEN_COOKIE_NAME", CUSTOM_ACCESS_COOKIE_NAME)
    organization = await OrganizationRepository(db_session).create(
        name="Playbook Athletics",
        slug="playbook",
    )
    user = await UserRepository(db_session).create(
        organization_id=organization.id,
        email="athlete@example.com",
        name="Jordan Athlete",
        auth_provider="google",
        provider_subject="google-subject",
        sport_team="Basketball",
    )
    token = jwt.encode({"sub": str(user.id)}, settings.SECRET_KEY, algorithm="HS256")

    response = await route_client.client.get(
        "/api/v1/users/me",
        headers={"Cookie": f"{CUSTOM_ACCESS_COOKIE_NAME}={token}"},
    )

    assert response.status_code == 200
    assert response.json()["id"] == str(user.id)
