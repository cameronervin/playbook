"""OAuth/OIDC provider adapters for Playbook authentication."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Literal, Protocol, cast
from urllib.parse import urlencode

from httpx_oauth.clients.google import GoogleOAuth2
from httpx_oauth.exceptions import GetProfileError
from httpx_oauth.oauth2 import HTTPXOAuthError, OAuth2Error

from app.auth.dev_personas import DevAuthPersona, Role, get_dev_user_spec
from app.core.config import Settings
from app.core.exceptions import ValidationError

ProviderName = Literal["google", "microsoft", "dev"]
_DISPLAY_NAME_WHITESPACE_RE = re.compile(r"\s+")
_GOOGLE_OIDC_SCOPES = ("openid", "profile", "email")
_GOOGLE_USERINFO_ENDPOINT = "https://openidconnect.googleapis.com/v1/userinfo"


class _GoogleUserInfoOAuth2(GoogleOAuth2):
    """Google OAuth client that reads login identity from OIDC userinfo."""

    def __init__(
        self,
        client_id: str,
        client_secret: str,
        scopes: list[str] | None = None,
        name: str = "google",
    ) -> None:
        super().__init__(
            client_id,
            client_secret,
            scopes=list(_GOOGLE_OIDC_SCOPES) if scopes is None else scopes,
            name=name,
        )

    async def get_profile(self, token: str) -> dict[str, object]:
        async with self.get_httpx_client() as client:
            response = await client.get(
                _GOOGLE_USERINFO_ENDPOINT,
                headers={**self.request_headers, "Authorization": f"Bearer {token}"},
            )

            if response.status_code >= 400:
                raise GetProfileError(response=response)

            return cast(dict[str, object], response.json())


@dataclass(frozen=True)
class OAuthIdentity:
    """Normalized provider identity returned after an OAuth callback."""

    provider: str
    subject: str
    email: str
    access_token: str
    expires_at: int | None = None
    refresh_token: str | None = None
    name: str | None = None
    role: Role | None = None
    sport_team: str | None = None
    persona: DevAuthPersona | None = None


@dataclass(frozen=True)
class ProviderDescriptor:
    """Public OAuth provider descriptor."""

    provider: ProviderName
    label: str
    enabled: bool
    login_url: str


class OAuthProviderCallbackError(Exception):
    """Raised when a provider callback cannot be exchanged for identity."""

    def __init__(
        self,
        *,
        phase: str = "callback",
        error_type: str = "OAuthProviderCallbackError",
        status_code: int | None = None,
    ) -> None:
        self.phase = phase
        self.error_type = error_type
        self.status_code = status_code
        super().__init__("OAuth provider callback failed")

    @classmethod
    def from_exception(
        cls,
        *,
        phase: str,
        exc: Exception,
    ) -> "OAuthProviderCallbackError":
        return cls(
            phase=phase,
            error_type=type(exc).__name__,
            status_code=_provider_status_code(exc),
        )


class OAuthProviderEmailMissingError(Exception):
    """Raised when the provider callback lacks an email address."""


class OAuthProviderClient(Protocol):
    """Provider client abstraction consumed by AuthService."""

    provider: ProviderName

    async def get_authorization_url(
        self,
        redirect_uri: str,
        *,
        state: str,
        persona: DevAuthPersona | None = None,
    ) -> str:
        """Return the provider authorization URL."""

    async def exchange_callback(
        self,
        *,
        code: str,
        redirect_uri: str,
    ) -> OAuthIdentity:
        """Exchange a provider callback code for normalized identity."""


class HTTPXOAuthProviderClient:
    """Adapter around httpx-oauth provider clients."""

    def __init__(self, provider: Literal["google", "microsoft"], raw_client) -> None:
        self.provider = provider
        self.raw_client = raw_client

    async def get_authorization_url(
        self,
        redirect_uri: str,
        *,
        state: str,
        persona: DevAuthPersona | None = None,
    ) -> str:
        if persona is not None:
            raise ValidationError(
                "Dev persona is only supported for Developer SSO",
                details={"provider": self.provider},
            )
        return await self.raw_client.get_authorization_url(redirect_uri, state=state)

    async def exchange_callback(
        self,
        *,
        code: str,
        redirect_uri: str,
    ) -> OAuthIdentity:
        try:
            token = await self.raw_client.get_access_token(code, redirect_uri)
            access_token = _required_token_value(token, "access_token")
        except (HTTPXOAuthError, OAuth2Error, TypeError, ValueError) as exc:
            raise OAuthProviderCallbackError.from_exception(
                phase="token_exchange",
                exc=exc,
            ) from exc

        try:
            profile = await self.raw_client.get_profile(access_token)
        except (HTTPXOAuthError, OAuth2Error, TypeError, ValueError) as exc:
            raise OAuthProviderCallbackError.from_exception(
                phase="profile_fetch",
                exc=exc,
            ) from exc

        try:
            account_id, account_email = _profile_identity(self.provider, profile)
            display_name = _profile_display_name(self.provider, profile)
        except (KeyError, TypeError, ValueError) as exc:
            raise OAuthProviderCallbackError.from_exception(
                phase="profile_parse",
                exc=exc,
            ) from exc

        if not account_email:
            raise OAuthProviderEmailMissingError

        return OAuthIdentity(
            provider=self.provider,
            subject=account_id,
            email=account_email,
            access_token=access_token,
            refresh_token=_optional_token_value(token, "refresh_token"),
            expires_at=_optional_token_expiry(token),
            name=display_name,
        )


class DevOAuthProviderClient:
    """Local-only fake SSO provider that exercises the normal OAuth routes."""

    provider: ProviderName = "dev"

    async def get_authorization_url(
        self,
        redirect_uri: str,
        *,
        state: str,
        persona: DevAuthPersona | None = None,
    ) -> str:
        resolved_persona = persona or "athlete"
        query = urlencode({"code": f"dev-{resolved_persona}", "state": state})
        return f"{redirect_uri}?{query}"

    async def exchange_callback(
        self,
        *,
        code: str,
        redirect_uri: str,
    ) -> OAuthIdentity:
        del redirect_uri
        if not code.startswith("dev-"):
            raise OAuthProviderCallbackError

        persona = code.removeprefix("dev-")
        if persona not in {"athlete", "new_athlete", "admin", "super_admin"}:
            raise OAuthProviderCallbackError

        spec = get_dev_user_spec(persona)  # type: ignore[arg-type]
        return OAuthIdentity(
            provider="dev",
            subject=f"phase1-{spec.key}",
            email=spec.email,
            access_token=f"dev-access-token-{spec.key}",
            refresh_token=None,
            expires_at=None,
            name=spec.name,
            role=spec.role,
            sport_team=spec.sport_team,
            persona=persona,  # type: ignore[arg-type]
        )


class OAuthProviderRegistry:
    """Create and describe OAuth provider clients from runtime settings."""

    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    def list_providers(self) -> list[ProviderDescriptor]:
        """Return the public provider list in product display order."""
        providers = [
            ProviderDescriptor(
                provider="google",
                label="Google",
                enabled=bool(
                    self.settings.GOOGLE_OAUTH_CLIENT_ID
                    and self.settings.GOOGLE_OAUTH_CLIENT_SECRET
                ),
                login_url="/api/v1/auth/google/login",
            ),
            ProviderDescriptor(
                provider="microsoft",
                label="Microsoft",
                enabled=bool(
                    self.settings.MICROSOFT_OAUTH_CLIENT_ID
                    and self.settings.MICROSOFT_OAUTH_CLIENT_SECRET
                ),
                login_url="/api/v1/auth/microsoft/login",
            ),
        ]
        if self.settings.dev_auth_available():
            providers.append(
                ProviderDescriptor(
                    provider="dev",
                    label="Developer SSO",
                    enabled=True,
                    login_url="/api/v1/auth/dev/login",
                )
            )
        return providers

    def get_client(self, provider: ProviderName) -> OAuthProviderClient:
        """Return an enabled provider client or raise a validation error."""
        if provider == "google":
            if not (
                self.settings.GOOGLE_OAUTH_CLIENT_ID
                and self.settings.GOOGLE_OAUTH_CLIENT_SECRET
            ):
                raise self._provider_not_configured(provider)
            return HTTPXOAuthProviderClient(
                provider,
                _GoogleUserInfoOAuth2(
                    self.settings.GOOGLE_OAUTH_CLIENT_ID,
                    self.settings.GOOGLE_OAUTH_CLIENT_SECRET,
                ),
            )
        if provider == "microsoft":
            if not (
                self.settings.MICROSOFT_OAUTH_CLIENT_ID
                and self.settings.MICROSOFT_OAUTH_CLIENT_SECRET
            ):
                raise self._provider_not_configured(provider)
            from httpx_oauth.clients.microsoft import MicrosoftGraphOAuth2

            return HTTPXOAuthProviderClient(
                provider,
                MicrosoftGraphOAuth2(
                    self.settings.MICROSOFT_OAUTH_CLIENT_ID,
                    self.settings.MICROSOFT_OAUTH_CLIENT_SECRET,
                    tenant=self.settings.MICROSOFT_OAUTH_TENANT,
                ),
            )
        if provider == "dev" and self.settings.dev_auth_available():
            return DevOAuthProviderClient()
        raise self._provider_not_configured(provider)

    @staticmethod
    def _provider_not_configured(provider: ProviderName) -> ValidationError:
        return ValidationError(
            f"OAuth provider '{provider}' is not configured",
            details={"provider": provider},
        )


def _required_token_value(token: object, key: str) -> str:
    if not isinstance(token, dict):
        raise TypeError("OAuth token payload was not a mapping")
    value = token.get(key)
    if not isinstance(value, str) or not value:
        raise ValueError(f"OAuth token payload missing {key}")
    return value


def _optional_token_value(token: object, key: str) -> str | None:
    if not isinstance(token, dict):
        return None
    value = token.get(key)
    return value if isinstance(value, str) and value else None


def _optional_token_expiry(token: object) -> int | None:
    if not isinstance(token, dict):
        return None
    value = token.get("expires_at")
    return value if isinstance(value, int) else None


def _profile_identity(
    provider: Literal["google", "microsoft"],
    profile: object,
) -> tuple[str, str | None]:
    if not isinstance(profile, dict):
        raise TypeError("OAuth profile payload was not a mapping")
    if provider == "google":
        return _google_profile_identity(profile)
    return _microsoft_profile_identity(profile)


def _google_profile_identity(profile: dict[object, object]) -> tuple[str, str | None]:
    subject = _required_profile_string(profile, "sub")
    email = _normalized_string(profile.get("email"))
    return subject, email


def _microsoft_profile_identity(profile: dict[object, object]) -> tuple[str, str | None]:
    subject = _required_profile_string(profile, "id")
    email = _normalized_string(profile.get("userPrincipalName"))
    return subject, email


def _profile_display_name(
    provider: Literal["google", "microsoft"],
    profile: object,
) -> str | None:
    if not isinstance(profile, dict):
        return None
    if provider == "google":
        return _google_profile_display_name(profile)
    return _normalized_string(profile.get("displayName"))


def _google_profile_display_name(profile: dict[object, object]) -> str | None:
    display_name = _normalized_string(profile.get("name"))
    if display_name is not None:
        return display_name
    parts = [
        part
        for part in (
            _normalized_string(profile.get("given_name")),
            _normalized_string(profile.get("family_name")),
        )
        if part is not None
    ]
    return _normalized_string(" ".join(parts)) if parts else None


def _required_profile_string(profile: dict[object, object], key: str) -> str:
    value = _normalized_string(profile.get(key))
    if value is None:
        raise ValueError(f"OAuth profile payload missing {key}")
    return value


def _normalized_string(value: object) -> str | None:
    if not isinstance(value, str):
        return None
    normalized = _DISPLAY_NAME_WHITESPACE_RE.sub(" ", value).strip()
    return normalized or None


def _provider_status_code(exc: Exception) -> int | None:
    response = getattr(exc, "response", None)
    status_code = getattr(response, "status_code", None)
    return status_code if isinstance(status_code, int) else None
