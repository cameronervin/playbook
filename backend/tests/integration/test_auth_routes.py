"""Route-level tests for Phase 1 authentication endpoints."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from urllib.parse import urlencode

import jwt
import pytest
from httpx_oauth.oauth2 import OAuth2Error
from sqlalchemy import select
from structlog.processors import format_exc_info
from structlog.testing import capture_logs

from app.api.v1.dependencies import get_auth_service
from app.core.config import Settings
from app.infrastructure.auth import OAuthIdentity
from app.models.identity import AppSession, OAuthAccount, User
from app.repositories.identity import (
    AppSessionRepository,
    OrganizationRepository,
    UserRepository,
)
from app.services.auth_service import AuthService

CUSTOM_ACCESS_COOKIE_NAME = "playbook_session"
DEFAULT_ACCESS_COOKIE_NAME = "access_token"
TOKEN_EXPIRY = 999999


class FakeOAuthProviderClient:
    """Tiny provider adapter fake matching the infrastructure auth protocol."""

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

    async def get_authorization_url(
        self,
        redirect_uri: str,
        *,
        state: str,
        persona: str | None = None,
    ) -> str:
        assert persona is None
        self.last_redirect_uri = redirect_uri
        self.last_state = state
        query = urlencode({"redirect_uri": redirect_uri, "state": state})
        return f"https://oauth.example/{self.provider}/authorize?{query}"

    async def exchange_callback(
        self,
        *,
        code: str,
        redirect_uri: str,
    ) -> OAuthIdentity:
        self.last_redirect_uri = redirect_uri
        if self.fail_identity_lookup:
            raise OAuth2Error(
                "provider identity failed "
                f"{self.access_token} {self.refresh_token}"
            )
        return OAuthIdentity(
            provider=self.provider,
            subject=self.subject,
            email=self.email,
            access_token=self.access_token,
            refresh_token=self.refresh_token,
            expires_at=TOKEN_EXPIRY,
        )


class FakeProviderRegistry:
    """Provider registry fake that returns protocol-level provider clients."""

    def __init__(self) -> None:
        self.clients = {
            "google": FakeOAuthProviderClient("google"),
            "microsoft": FakeOAuthProviderClient("microsoft"),
        }

    def list_providers(self):
        return [
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

    def get_client(self, provider: str):
        return self.clients[provider]


def _configure_oauth_settings(
    monkeypatch: pytest.MonkeyPatch,
    settings: Settings,
) -> None:
    monkeypatch.setattr(settings, "COOKIE_DOMAIN", "")
    monkeypatch.setattr(settings, "GOOGLE_OAUTH_CLIENT_ID", "google-client")
    monkeypatch.setattr(settings, "GOOGLE_OAUTH_CLIENT_SECRET", "google-secret")
    monkeypatch.setattr(settings, "MICROSOFT_OAUTH_CLIENT_ID", "microsoft-client")
    monkeypatch.setattr(settings, "MICROSOFT_OAUTH_CLIENT_SECRET", "microsoft-secret")


def _override_auth_service_with_registry(
    route_client,
    db_session,
    provider_registry,
    settings: Settings,
) -> None:
    def override_auth_service() -> AuthService:
        return AuthService(
            db_session,
            settings=settings,
            provider_registry=provider_registry,
        )

    route_client.app.dependency_overrides[get_auth_service] = override_auth_service


def _log_blob(captured_logs: list[dict[str, object]]) -> str:
    return " ".join(str(entry) for entry in captured_logs)


@pytest.mark.asyncio
async def test_auth_provider_listing_uses_configured_providers(
    route_client,
    monkeypatch,
    test_settings,
) -> None:
    monkeypatch.setattr(test_settings, "GOOGLE_OAUTH_CLIENT_ID", "google-client")
    monkeypatch.setattr(test_settings, "GOOGLE_OAUTH_CLIENT_SECRET", "google-secret")
    monkeypatch.setattr(test_settings, "MICROSOFT_OAUTH_CLIENT_ID", "microsoft-client")
    monkeypatch.setattr(test_settings, "MICROSOFT_OAUTH_CLIENT_SECRET", "microsoft-secret")

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
async def test_auth_provider_listing_includes_dev_provider_only_when_available(
    route_client,
    monkeypatch,
    test_settings,
) -> None:
    _configure_oauth_settings(monkeypatch, test_settings)

    disabled_response = await route_client.client.get("/api/v1/auth/providers")

    monkeypatch.setattr(test_settings, "DEV_AUTH_ENABLED", True)
    monkeypatch.setattr(test_settings, "ENVIRONMENT", "local")
    monkeypatch.setattr(test_settings, "DEBUG", True)
    enabled_response = await route_client.client.get("/api/v1/auth/providers")

    assert disabled_response.status_code == 200
    assert [provider["provider"] for provider in disabled_response.json()["providers"]] == [
        "google",
        "microsoft",
    ]
    assert enabled_response.status_code == 200
    assert enabled_response.json()["providers"][-1] == {
        "provider": "dev",
        "label": "Developer SSO",
        "enabled": True,
        "login_url": "/api/v1/auth/dev/login",
    }


@pytest.mark.asyncio
@pytest.mark.parametrize("provider", ["google", "microsoft"])
async def test_oauth_callback_creates_session_without_exposing_provider_tokens(
    route_client,
    db_session,
    monkeypatch,
    test_settings,
    provider,
) -> None:
    _configure_oauth_settings(monkeypatch, test_settings)
    monkeypatch.setattr(test_settings, "ACCESS_TOKEN_COOKIE_NAME", CUSTOM_ACCESS_COOKIE_NAME)
    provider_registry = FakeProviderRegistry()
    _override_auth_service_with_registry(
        route_client,
        db_session,
        provider_registry,
        test_settings,
    )

    login_response = await route_client.client.get(f"/api/v1/auth/{provider}/login")
    oauth_client = provider_registry.clients[provider]

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
    decoded_token = jwt.decode(body["access_token"], test_settings.SECRET_KEY, algorithms=["HS256"])
    assert decoded_token["sub"]
    assert decoded_token["sid"]
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
    app_session = await db_session.scalar(
        select(AppSession).where(AppSession.user_id == user.id)
    )
    assert account is not None
    assert user is not None
    assert app_session is not None
    assert decoded_token["sid"] == str(app_session.id)
    assert app_session.revoked_at is None
    assert account.user_id == user.id
    assert account.access_token == oauth_client.access_token
    assert account.refresh_token == oauth_client.refresh_token
    assert account.expires_at == TOKEN_EXPIRY
    assert user.auth_provider == provider
    assert user.provider_subject == oauth_client.subject


@pytest.mark.asyncio
@pytest.mark.parametrize("role", ["admin", "super_admin"])
async def test_oauth_callback_sends_admin_roles_to_admin_workspace(
    route_client,
    db_session,
    monkeypatch,
    test_settings,
    role: str,
) -> None:
    _configure_oauth_settings(monkeypatch, test_settings)
    provider_registry = FakeProviderRegistry()
    _override_auth_service_with_registry(
        route_client,
        db_session,
        provider_registry,
        test_settings,
    )
    oauth_client = provider_registry.clients["google"]
    organization = await OrganizationRepository(db_session).create(
        name=test_settings.DEFAULT_ORGANIZATION_NAME,
        slug=test_settings.DEFAULT_ORGANIZATION_SLUG,
    )
    await UserRepository(db_session).create(
        organization_id=organization.id,
        email=oauth_client.email,
        name="Jordan Admin",
        auth_provider="google",
        provider_subject="existing-google-subject",
        role=role,
    )

    login_response = await route_client.client.get("/api/v1/auth/google/login")
    assert login_response.status_code == 200
    assert oauth_client.last_state is not None

    callback_response = await route_client.client.get(
        "/api/v1/auth/google/callback",
        params={"code": "oauth-code", "state": oauth_client.last_state},
    )

    assert callback_response.status_code == 200
    assert callback_response.json()["user"]["role"] == role
    assert callback_response.json()["next_route"] == "/admin"


@pytest.mark.asyncio
async def test_oauth_callback_redirects_browser_callers_after_setting_cookie(
    route_client,
    db_session,
    monkeypatch,
    test_settings,
) -> None:
    _configure_oauth_settings(monkeypatch, test_settings)
    monkeypatch.setattr(test_settings, "FRONTEND_URL", "http://localhost:3000")
    monkeypatch.setattr(test_settings, "ACCESS_TOKEN_COOKIE_NAME", CUSTOM_ACCESS_COOKIE_NAME)
    provider_registry = FakeProviderRegistry()
    _override_auth_service_with_registry(
        route_client,
        db_session,
        provider_registry,
        test_settings,
    )

    login_response = await route_client.client.get("/api/v1/auth/google/login")
    google_client = provider_registry.clients["google"]
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
    assert f"{test_settings.OAUTH_STATE_COOKIE_NAME}=" in set_cookie
    assert "Max-Age=0" in set_cookie


@pytest.mark.asyncio
async def test_oauth_callback_failure_does_not_persist_or_log_provider_tokens(
    route_client,
    db_session,
    monkeypatch,
    test_settings,
) -> None:
    _configure_oauth_settings(monkeypatch, test_settings)
    monkeypatch.setattr(test_settings, "ACCESS_TOKEN_COOKIE_NAME", CUSTOM_ACCESS_COOKIE_NAME)
    provider_registry = FakeProviderRegistry()
    provider_registry.clients["google"].fail_identity_lookup = True
    _override_auth_service_with_registry(
        route_client,
        db_session,
        provider_registry,
        test_settings,
    )

    login_response = await route_client.client.get("/api/v1/auth/google/login")
    google_client = provider_registry.clients["google"]
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
    test_settings,
    provider,
) -> None:
    _configure_oauth_settings(monkeypatch, test_settings)
    provider_registry = FakeProviderRegistry()
    _override_auth_service_with_registry(
        route_client,
        db_session,
        provider_registry,
        test_settings,
    )

    response = await route_client.client.get(f"/api/v1/auth/{provider}/login")

    assert response.status_code == 200
    assert f"https://oauth.example/{provider}/authorize" in response.json()[
        "authorization_url"
    ]


@pytest.mark.asyncio
async def test_dev_oauth_login_and_callback_create_super_admin_session(
    route_client,
    db_session,
    monkeypatch,
    test_settings,
) -> None:
    monkeypatch.setattr(test_settings, "COOKIE_DOMAIN", "")
    monkeypatch.setattr(test_settings, "DEV_AUTH_ENABLED", True)
    monkeypatch.setattr(test_settings, "ENVIRONMENT", "local")
    monkeypatch.setattr(test_settings, "DEBUG", True)
    monkeypatch.setattr(test_settings, "FRONTEND_URL", "http://localhost:3000")
    monkeypatch.setattr(test_settings, "ACCESS_TOKEN_COOKIE_NAME", CUSTOM_ACCESS_COOKIE_NAME)

    login_response = await route_client.client.get(
        "/api/v1/auth/dev/login",
        params={"persona": "super_admin"},
    )

    assert login_response.status_code == 200
    authorization_url = login_response.json()["authorization_url"]
    assert "/api/v1/auth/dev/callback" in authorization_url
    assert "code=dev-super_admin" in authorization_url
    assert "state=" in authorization_url

    callback_response = await route_client.client.get(
        authorization_url.replace("http://localhost:8000", ""),
        headers={"Accept": "text/html"},
        follow_redirects=False,
    )
    me_response = await route_client.client.get("/api/v1/users/me")

    assert callback_response.status_code == 303
    assert callback_response.headers["location"] == "http://localhost:3000/admin"
    assert f"{CUSTOM_ACCESS_COOKIE_NAME}=" in callback_response.headers["set-cookie"]
    assert me_response.status_code == 200
    assert me_response.json()["role"] == "super_admin"
    assert me_response.json()["email"] == "phase1-super@example.com"

    user = await db_session.scalar(
        select(User).where(User.email == "phase1-super@example.com")
    )
    assert user is not None
    assert user.auth_provider == "dev"
    assert user.provider_subject == "phase1-super_admin"
    assert user.is_superuser is True


@pytest.mark.asyncio
async def test_dev_oauth_login_defaults_to_athlete_persona(
    route_client,
    monkeypatch,
    test_settings,
) -> None:
    monkeypatch.setattr(test_settings, "COOKIE_DOMAIN", "")
    monkeypatch.setattr(test_settings, "DEV_AUTH_ENABLED", True)
    monkeypatch.setattr(test_settings, "ENVIRONMENT", "local")
    monkeypatch.setattr(test_settings, "DEBUG", True)

    login_response = await route_client.client.get("/api/v1/auth/dev/login")

    assert login_response.status_code == 200
    assert "code=dev-athlete" in login_response.json()["authorization_url"]


@pytest.mark.asyncio
async def test_dev_oauth_login_is_unavailable_when_dev_auth_is_disabled(
    route_client,
    monkeypatch,
    test_settings,
) -> None:
    monkeypatch.setattr(test_settings, "DEV_AUTH_ENABLED", False)
    monkeypatch.setattr(test_settings, "ENVIRONMENT", "local")
    monkeypatch.setattr(test_settings, "DEBUG", True)

    response = await route_client.client.get("/api/v1/auth/dev/login")

    assert response.status_code == 400
    assert response.json()["error"]["code"] == "VALIDATION_ERROR"


@pytest.mark.asyncio
async def test_real_oauth_login_rejects_dev_persona_query(
    route_client,
    db_session,
    monkeypatch,
    test_settings,
) -> None:
    _configure_oauth_settings(monkeypatch, test_settings)
    provider_registry = FakeProviderRegistry()
    _override_auth_service_with_registry(
        route_client,
        db_session,
        provider_registry,
        test_settings,
    )

    response = await route_client.client.get(
        "/api/v1/auth/google/login",
        params={"persona": "admin"},
    )

    assert response.status_code == 400
    assert response.json()["error"]["code"] == "VALIDATION_ERROR"


@pytest.mark.asyncio
async def test_authenticated_activity_refreshes_near_expiry_session_cookie(
    route_client,
    db_session,
    monkeypatch,
    test_settings,
) -> None:
    monkeypatch.setattr(test_settings, "COOKIE_DOMAIN", "")
    monkeypatch.setattr(test_settings, "ACCESS_TOKEN_COOKIE_NAME", CUSTOM_ACCESS_COOKIE_NAME)
    monkeypatch.setattr(test_settings, "JWT_LIFETIME_SECONDS", 3600)
    monkeypatch.setattr(test_settings, "JWT_REFRESH_THRESHOLD_SECONDS", 1800)
    organization = await OrganizationRepository(db_session).create(
        name="Playbook Athletics",
        slug="playbook-refresh",
    )
    user = await UserRepository(db_session).create(
        organization_id=organization.id,
        email="athlete-refresh@example.com",
        name="Jordan Athlete",
        auth_provider="google",
        provider_subject="google-refresh-subject",
        sport_team="Basketball",
    )
    original_expiry = datetime.now(UTC) + timedelta(seconds=30)
    app_session = await AppSessionRepository(db_session).create(
        user_id=user.id,
        expires_at=original_expiry,
    )
    token = jwt.encode(
        {
            "sub": str(user.id),
            "sid": str(app_session.id),
            "role": user.role,
            "iat": int(datetime.now(UTC).timestamp()),
            "exp": int(original_expiry.timestamp()),
        },
        test_settings.SECRET_KEY,
        algorithm="HS256",
    )

    response = await route_client.client.get(
        "/api/v1/users/me",
        headers={"Cookie": f"{CUSTOM_ACCESS_COOKIE_NAME}={token}"},
    )
    await db_session.refresh(app_session)

    assert response.status_code == 200
    assert f"{CUSTOM_ACCESS_COOKIE_NAME}=" in response.headers["set-cookie"]
    refreshed_token = route_client.client.cookies.get(CUSTOM_ACCESS_COOKIE_NAME)
    assert refreshed_token is not None
    refreshed_payload = jwt.decode(
        refreshed_token,
        test_settings.SECRET_KEY,
        algorithms=["HS256"],
    )
    assert refreshed_payload["sid"] == str(app_session.id)
    assert refreshed_payload["exp"] > int(original_expiry.timestamp())
    assert app_session.expires_at > original_expiry
    assert app_session.last_seen_at is not None


@pytest.mark.asyncio
async def test_expired_session_cookie_is_cleared_with_structured_unauthorized(
    route_client,
    db_session,
    monkeypatch,
    test_settings,
) -> None:
    monkeypatch.setattr(test_settings, "COOKIE_DOMAIN", "")
    monkeypatch.setattr(test_settings, "ACCESS_TOKEN_COOKIE_NAME", CUSTOM_ACCESS_COOKIE_NAME)
    organization = await OrganizationRepository(db_session).create(
        name="Playbook Athletics",
        slug="playbook-expired",
    )
    user = await UserRepository(db_session).create(
        organization_id=organization.id,
        email="athlete-expired@example.com",
        name="Jordan Athlete",
        auth_provider="google",
        provider_subject="google-expired-subject",
        sport_team="Basketball",
    )
    expired_at = datetime.now(UTC) - timedelta(seconds=30)
    app_session = await AppSessionRepository(db_session).create(
        user_id=user.id,
        expires_at=expired_at,
    )
    token = jwt.encode(
        {
            "sub": str(user.id),
            "sid": str(app_session.id),
            "role": user.role,
            "iat": int((expired_at - timedelta(minutes=5)).timestamp()),
            "exp": int(expired_at.timestamp()),
        },
        test_settings.SECRET_KEY,
        algorithm="HS256",
    )

    response = await route_client.client.get(
        "/api/v1/users/me",
        headers={"Cookie": f"{CUSTOM_ACCESS_COOKIE_NAME}={token}"},
    )

    assert response.status_code == 401
    assert response.json()["error"]["code"] == "UNAUTHORIZED"
    assert response.json()["error"]["details"]["reason"] == "session_expired"
    assert f"{CUSTOM_ACCESS_COOKIE_NAME}=" in response.headers["set-cookie"]
    assert "Max-Age=0" in response.headers["set-cookie"]


@pytest.mark.asyncio
async def test_session_refresh_endpoint_renews_activity_without_response_body(
    route_client,
    db_session,
    monkeypatch,
    test_settings,
) -> None:
    monkeypatch.setattr(test_settings, "COOKIE_DOMAIN", "")
    monkeypatch.setattr(test_settings, "ACCESS_TOKEN_COOKIE_NAME", CUSTOM_ACCESS_COOKIE_NAME)
    organization = await OrganizationRepository(db_session).create(
        name="Playbook Athletics",
        slug="playbook-refresh-endpoint",
    )
    user = await UserRepository(db_session).create(
        organization_id=organization.id,
        email="refresh-endpoint@example.com",
        name="Jordan Athlete",
        auth_provider="google",
        provider_subject="google-refresh-endpoint",
        sport_team="Basketball",
    )
    original_expiry = datetime.now(UTC) + timedelta(seconds=20)
    app_session = await AppSessionRepository(db_session).create(
        user_id=user.id,
        expires_at=original_expiry,
    )
    token = jwt.encode(
        {
            "sub": str(user.id),
            "sid": str(app_session.id),
            "role": user.role,
            "iat": int(datetime.now(UTC).timestamp()),
            "exp": int(original_expiry.timestamp()),
        },
        test_settings.SECRET_KEY,
        algorithm="HS256",
    )

    response = await route_client.client.post(
        "/api/v1/auth/session/refresh",
        headers={"Cookie": f"{CUSTOM_ACCESS_COOKIE_NAME}={token}"},
    )

    assert response.status_code == 204
    assert response.text == ""
    assert f"{CUSTOM_ACCESS_COOKIE_NAME}=" in response.headers["set-cookie"]


@pytest.mark.asyncio
async def test_logout_revokes_app_session_and_clears_configured_cookie(
    route_client,
    db_session,
    monkeypatch,
    test_settings,
) -> None:
    monkeypatch.setattr(test_settings, "COOKIE_DOMAIN", "")
    monkeypatch.setattr(test_settings, "ACCESS_TOKEN_COOKIE_NAME", CUSTOM_ACCESS_COOKIE_NAME)
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
        test_settings.SECRET_KEY,
        algorithm="HS256",
    )

    unauthenticated = await route_client.client.post("/api/v1/auth/logout")
    authenticated = await route_client.client.post(
        "/api/v1/auth/logout",
        headers={"Cookie": f"{CUSTOM_ACCESS_COOKIE_NAME}={token}"},
    )
    await db_session.refresh(app_session)

    assert unauthenticated.status_code == 200
    assert unauthenticated.json() == {"status": "ok"}
    assert authenticated.status_code == 200
    assert authenticated.json() == {"status": "ok"}
    assert app_session.revoked_at is not None
    assert app_session.revoked_reason == "logout"
    assert f"{CUSTOM_ACCESS_COOKIE_NAME}=" in authenticated.headers["set-cookie"]
    assert "Max-Age=0" in authenticated.headers["set-cookie"]


@pytest.mark.asyncio
async def test_current_user_dependency_accepts_configured_cookie_name(
    route_client,
    db_session,
    monkeypatch,
    test_settings,
) -> None:
    monkeypatch.setattr(test_settings, "ACCESS_TOKEN_COOKIE_NAME", CUSTOM_ACCESS_COOKIE_NAME)
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
        test_settings.SECRET_KEY,
        algorithm="HS256",
    )

    response = await route_client.client.get(
        "/api/v1/users/me",
        headers={"Cookie": f"{CUSTOM_ACCESS_COOKIE_NAME}={token}"},
    )

    assert response.status_code == 200
    assert response.json()["id"] == str(user.id)
