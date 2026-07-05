"""OAuth provider profile normalization tests."""

from __future__ import annotations

from urllib.parse import parse_qs, urlparse

import pytest
from httpx_oauth.exceptions import GetProfileError

from app.infrastructure.auth.providers import (
    HTTPXOAuthProviderClient,
    OAuthProviderCallbackError,
    _GoogleUserInfoOAuth2,
)

TOKEN_EXPIRY = 999999


class FakeRawOAuthClient:
    def __init__(self, profile: dict[str, object]) -> None:
        self.profile = profile
        self.profile_token: str | None = None

    async def get_access_token(self, code: str, redirect_uri: str) -> dict[str, object]:
        return {
            "access_token": f"{code}-access-token",
            "refresh_token": "provider-refresh-token",
            "expires_at": TOKEN_EXPIRY,
        }

    async def get_profile(self, token: str) -> dict[str, object]:
        self.profile_token = token
        return self.profile


class FakeProfileResponse:
    def __init__(self, payload: dict[str, object], *, status_code: int = 200) -> None:
        self.payload = payload
        self.status_code = status_code

    def json(self) -> dict[str, object]:
        return self.payload


class FakeHTTPXClient:
    def __init__(self, response: FakeProfileResponse) -> None:
        self.response = response
        self.requests: list[dict[str, object]] = []

    async def __aenter__(self) -> "FakeHTTPXClient":
        return self

    async def __aexit__(self, *args: object) -> None:
        return None

    async def get(
        self,
        endpoint: str,
        *,
        headers: dict[str, str],
        params: dict[str, str] | None = None,
    ) -> FakeProfileResponse:
        self.requests.append({"endpoint": endpoint, "params": params, "headers": headers})
        return self.response


@pytest.mark.asyncio
async def test_google_profile_client_requests_oidc_userinfo_without_people_fields() -> None:
    response = FakeProfileResponse(
        {
            "sub": "google-oidc-subject",
            "email": "athlete@example.edu",
            "name": "Jordan Mitchell",
        }
    )
    fake_httpx = FakeHTTPXClient(response)
    client = _GoogleUserInfoOAuth2("google-client", "google-secret")
    client.get_httpx_client = lambda: fake_httpx  # type: ignore[method-assign]

    profile = await client.get_profile("provider-access-token")

    assert profile == response.payload
    assert fake_httpx.requests == [
        {
            "endpoint": "https://openidconnect.googleapis.com/v1/userinfo",
            "params": None,
            "headers": {
                "Accept": "application/json",
                "Authorization": "Bearer provider-access-token",
            },
        }
    ]


@pytest.mark.asyncio
async def test_google_profile_client_requests_openid_profile_email_scopes() -> None:
    client = _GoogleUserInfoOAuth2("google-client", "google-secret")

    authorization_url = await client.get_authorization_url(
        "https://api.example/auth/google/callback",
        state="csrf-state",
    )

    query = parse_qs(urlparse(authorization_url).query)
    assert query["scope"] == ["openid profile email"]


@pytest.mark.asyncio
async def test_google_oauth_identity_uses_primary_profile_display_name() -> None:
    raw_client = FakeRawOAuthClient(
        {
            "sub": "google-oidc-subject",
            "email": "athlete@example.edu",
            "name": "  Jordan   Mitchell  ",
        }
    )
    client = HTTPXOAuthProviderClient("google", raw_client)

    identity = await client.exchange_callback(
        code="oauth-code",
        redirect_uri="https://api.example/auth/google/callback",
    )

    assert identity.subject == "google-oidc-subject"
    assert identity.email == "athlete@example.edu"
    assert identity.name == "Jordan Mitchell"
    assert raw_client.profile_token == "oauth-code-access-token"


@pytest.mark.asyncio
async def test_google_oauth_identity_falls_back_to_given_and_family_name() -> None:
    raw_client = FakeRawOAuthClient(
        {
            "sub": "google-oidc-subject",
            "email": "athlete@example.edu",
            "given_name": "  Jordan ",
            "family_name": " Mitchell  ",
        }
    )
    client = HTTPXOAuthProviderClient("google", raw_client)

    identity = await client.exchange_callback(
        code="oauth-code",
        redirect_uri="https://api.example/auth/google/callback",
    )

    assert identity.subject == "google-oidc-subject"
    assert identity.email == "athlete@example.edu"
    assert identity.name == "Jordan Mitchell"


@pytest.mark.asyncio
async def test_google_oauth_identity_allows_missing_profile_display_name() -> None:
    raw_client = FakeRawOAuthClient(
        {
            "sub": "google-oidc-subject",
            "email": "athlete@example.edu",
        }
    )
    client = HTTPXOAuthProviderClient("google", raw_client)

    identity = await client.exchange_callback(
        code="oauth-code",
        redirect_uri="https://api.example/auth/google/callback",
    )

    assert identity.email == "athlete@example.edu"
    assert identity.name is None


@pytest.mark.asyncio
async def test_microsoft_oauth_identity_uses_graph_display_name() -> None:
    raw_client = FakeRawOAuthClient(
        {
            "id": "microsoft-subject",
            "userPrincipalName": "athlete@example.edu",
            "mail": "athlete-mail@example.edu",
            "displayName": "  Jordan   Mitchell  ",
        }
    )
    client = HTTPXOAuthProviderClient("microsoft", raw_client)

    identity = await client.exchange_callback(
        code="oauth-code",
        redirect_uri="https://api.example/auth/microsoft/callback",
    )

    assert identity.subject == "microsoft-subject"
    assert identity.email == "athlete@example.edu"
    assert identity.name == "Jordan Mitchell"
    assert raw_client.profile_token == "oauth-code-access-token"


@pytest.mark.asyncio
async def test_oauth_identity_allows_missing_profile_display_name() -> None:
    raw_client = FakeRawOAuthClient(
        {
            "id": "microsoft-subject",
            "userPrincipalName": "athlete@example.edu",
            "displayName": "   ",
        }
    )
    client = HTTPXOAuthProviderClient("microsoft", raw_client)

    identity = await client.exchange_callback(
        code="oauth-code",
        redirect_uri="https://api.example/auth/microsoft/callback",
    )

    assert identity.email == "athlete@example.edu"
    assert identity.name is None


@pytest.mark.asyncio
async def test_oauth_identity_profile_fetch_failure_exposes_safe_diagnostics() -> None:
    class FailingRawOAuthClient(FakeRawOAuthClient):
        async def get_profile(self, token: str) -> dict[str, object]:
            self.profile_token = token
            raise GetProfileError(
                response=FakeProfileResponse(
                    {"error": "do not log provider body"},
                    status_code=403,
                )
            )

    raw_client = FailingRawOAuthClient({})
    client = HTTPXOAuthProviderClient("google", raw_client)

    with pytest.raises(OAuthProviderCallbackError) as exc_info:
        await client.exchange_callback(
            code="oauth-code",
            redirect_uri="https://api.example/auth/google/callback",
        )

    error = exc_info.value
    assert error.phase == "profile_fetch"
    assert error.error_type == "GetProfileError"
    assert error.status_code == 403
    assert "oauth-code-access-token" not in str(error)
    assert "do not log provider body" not in str(error)
