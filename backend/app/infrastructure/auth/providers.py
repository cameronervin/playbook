"""OAuth/OIDC provider adapters for Playbook authentication."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal, Protocol
from urllib.parse import urlencode

from httpx_oauth.oauth2 import HTTPXOAuthError, OAuth2Error

from app.auth.dev_personas import DevAuthPersona, Role, get_dev_user_spec
from app.core.config import Settings
from app.core.exceptions import ValidationError

ProviderName = Literal["google", "microsoft", "dev"]


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
            account_id, account_email = await self.raw_client.get_id_email(
                token["access_token"]
            )
        except (HTTPXOAuthError, OAuth2Error) as exc:
            raise OAuthProviderCallbackError from exc

        if not account_email:
            raise OAuthProviderEmailMissingError

        return OAuthIdentity(
            provider=self.provider,
            subject=account_id,
            email=account_email,
            access_token=token["access_token"],
            refresh_token=token.get("refresh_token"),
            expires_at=token.get("expires_at"),
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
            from httpx_oauth.clients.google import GoogleOAuth2

            return HTTPXOAuthProviderClient(
                provider,
                GoogleOAuth2(
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
