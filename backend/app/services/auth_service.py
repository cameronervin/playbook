"""OAuth/OIDC authentication service."""

from __future__ import annotations

import secrets
from datetime import UTC, datetime, timedelta
from typing import Any, Literal

import jwt
import structlog
from fastapi import Request, Response
from httpx_oauth.oauth2 import HTTPXOAuthError, OAuth2Error
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import AUTH_COOKIE_NAME, is_profile_complete
from app.core.config import settings
from app.core.exceptions import OAuthError, ValidationError
from app.models.identity import User
from app.repositories.identity import (
    OAuthAccountRepository,
    OrganizationRepository,
    UserRepository,
)
from app.schemas.users import (
    AuthProviderResponse,
    AuthProvidersResponse,
    OAuthLoginResponse,
    SessionResponse,
    UserResponse,
)

logger = structlog.get_logger(__name__)

ProviderName = Literal["google", "microsoft"]
_STATE_COOKIE_MAX_AGE = 600


def create_access_token(user: User) -> str:
    """Create the app JWT used by Playbook API dependencies."""
    now = datetime.now(UTC)
    payload = {
        "sub": str(user.id),
        "role": user.role,
        "iat": int(now.timestamp()),
        "exp": int((now + timedelta(seconds=settings.JWT_LIFETIME_SECONDS)).timestamp()),
    }
    return jwt.encode(payload, settings.SECRET_KEY, algorithm="HS256")


def user_to_response(user: User) -> UserResponse:
    """Map a User ORM object to a public user DTO."""
    return UserResponse(
        id=user.id,
        organization_id=user.organization_id,
        email=user.email,
        name=user.name,
        role=user.role,  # type: ignore[arg-type]
        sport_team=user.sport_team,
        profile_complete=is_profile_complete(user),
        is_active=user.is_active,
        created_at=user.created_at,
    )


def _cookie_domain() -> str | None:
    return settings.COOKIE_DOMAIN or None


def set_access_token_cookie(response: Response, token: str) -> None:
    """Attach the app access token as an HttpOnly cookie."""
    response.set_cookie(
        AUTH_COOKIE_NAME,
        token,
        max_age=settings.JWT_LIFETIME_SECONDS,
        httponly=True,
        secure=settings.ENVIRONMENT.lower() in {"prod", "production"},
        samesite="lax",
        domain=_cookie_domain(),
    )


class OAuthClientFactory:
    """Create OAuth clients lazily so optional provider setup stays cheap."""

    def get_client(self, provider: ProviderName):
        if provider == "google":
            from httpx_oauth.clients.google import GoogleOAuth2

            return GoogleOAuth2(
                settings.GOOGLE_OAUTH_CLIENT_ID,
                settings.GOOGLE_OAUTH_CLIENT_SECRET,
            )
        if provider == "microsoft":
            from httpx_oauth.clients.microsoft import MicrosoftGraphOAuth2

            return MicrosoftGraphOAuth2(
                settings.MICROSOFT_OAUTH_CLIENT_ID,
                settings.MICROSOFT_OAUTH_CLIENT_SECRET,
                tenant=settings.MICROSOFT_OAUTH_TENANT,
            )
        raise ValidationError("Unsupported OAuth provider")


class AuthService:
    """Playbook OAuth and session orchestration."""

    def __init__(
        self,
        session: AsyncSession,
        *,
        org_repo: OrganizationRepository | None = None,
        user_repo: UserRepository | None = None,
        oauth_repo: OAuthAccountRepository | None = None,
        client_factory: OAuthClientFactory | None = None,
    ) -> None:
        self.session = session
        self.org_repo = org_repo or OrganizationRepository(session)
        self.user_repo = user_repo or UserRepository(session)
        self.oauth_repo = oauth_repo or OAuthAccountRepository(session)
        self.client_factory = client_factory or OAuthClientFactory()

    def providers(self) -> AuthProvidersResponse:
        """Return enabled OAuth providers."""
        providers = [
            AuthProviderResponse(
                provider="google",
                label="Google",
                enabled=bool(
                    settings.GOOGLE_OAUTH_CLIENT_ID
                    and settings.GOOGLE_OAUTH_CLIENT_SECRET
                ),
                login_url="/api/v1/auth/google/login",
            ),
            AuthProviderResponse(
                provider="microsoft",
                label="Microsoft",
                enabled=bool(
                    settings.MICROSOFT_OAUTH_CLIENT_ID
                    and settings.MICROSOFT_OAUTH_CLIENT_SECRET
                ),
                login_url="/api/v1/auth/microsoft/login",
            ),
        ]
        return AuthProvidersResponse(providers=providers)

    async def login_url(
        self,
        *,
        provider: ProviderName,
        request: Request,
        response: Response,
    ) -> OAuthLoginResponse:
        """Create an OAuth authorization URL and bind CSRF state in a cookie."""
        self._assert_provider_enabled(provider)
        csrf = secrets.token_urlsafe(32)
        now = datetime.now(UTC)
        state = jwt.encode(
            {
                "provider": provider,
                "csrf": csrf,
                "iat": int(now.timestamp()),
                "exp": int((now + timedelta(seconds=_STATE_COOKIE_MAX_AGE)).timestamp()),
            },
            settings.OAUTH_STATE_SECRET,
            algorithm="HS256",
        )
        response.set_cookie(
            settings.OAUTH_STATE_COOKIE_NAME,
            csrf,
            max_age=_STATE_COOKIE_MAX_AGE,
            httponly=True,
            secure=settings.ENVIRONMENT.lower() in {"prod", "production"},
            samesite="lax",
            domain=_cookie_domain(),
        )
        client = self.client_factory.get_client(provider)
        authorization_url = await client.get_authorization_url(
            self._redirect_uri(provider, request),
            state=state,
        )
        return OAuthLoginResponse(authorization_url=authorization_url)

    async def callback(
        self,
        *,
        provider: ProviderName,
        code: str,
        state: str,
        request: Request,
        response: Response,
    ) -> SessionResponse:
        """Handle OAuth callback, upsert user/account, and create a session."""
        self._assert_provider_enabled(provider)
        self._validate_state(provider=provider, state=state, request=request)
        client = self.client_factory.get_client(provider)
        try:
            token = await client.get_access_token(
                code,
                self._redirect_uri(provider, request),
            )
            account_id, account_email = await client.get_id_email(token["access_token"])
        except (HTTPXOAuthError, OAuth2Error) as exc:
            raise OAuthError(
                "OAuth provider callback failed",
                details={"provider": provider},
            ) from exc

        if not account_email:
            raise OAuthError(
                "OAuth provider did not return an email address",
                details={"provider": provider},
            )

        user = await self._upsert_user_from_oauth(
            provider=provider,
            account_id=account_id,
            account_email=account_email,
            token=token,
        )
        await self.session.commit()
        access_token = create_access_token(user)
        set_access_token_cookie(response, access_token)
        response.delete_cookie(
            settings.OAUTH_STATE_COOKIE_NAME,
            domain=_cookie_domain(),
        )
        logger.info(
            "auth_oauth_login_succeeded",
            provider=provider,
            user_id=str(user.id),
            organization_id=str(user.organization_id),
        )
        return SessionResponse(
            user=user_to_response(user),
            access_token=access_token,
            next_route="/chat" if is_profile_complete(user) else "/profile",
        )

    def logout(self, response: Response) -> None:
        """Clear the app access token cookie."""
        response.delete_cookie(AUTH_COOKIE_NAME, domain=_cookie_domain())

    def _assert_provider_enabled(self, provider: ProviderName) -> None:
        enabled = {
            "google": bool(
                settings.GOOGLE_OAUTH_CLIENT_ID and settings.GOOGLE_OAUTH_CLIENT_SECRET
            ),
            "microsoft": bool(
                settings.MICROSOFT_OAUTH_CLIENT_ID
                and settings.MICROSOFT_OAUTH_CLIENT_SECRET
            ),
        }[provider]
        if not enabled:
            raise ValidationError(
                f"OAuth provider '{provider}' is not configured",
                details={"provider": provider},
            )

    @staticmethod
    def _redirect_uri(provider: ProviderName, request: Request) -> str:
        base_url = settings.API_PUBLIC_URL.rstrip("/")
        if base_url:
            return f"{base_url}/api/v1/auth/{provider}/callback"
        return str(request.base_url).rstrip("/") + f"/api/v1/auth/{provider}/callback"

    def _validate_state(
        self,
        *,
        provider: ProviderName,
        state: str,
        request: Request,
    ) -> None:
        try:
            payload = jwt.decode(
                state,
                settings.OAUTH_STATE_SECRET,
                algorithms=["HS256"],
            )
        except jwt.PyJWTError as exc:
            raise ValidationError("Invalid OAuth state") from exc

        cookie_csrf = request.cookies.get(settings.OAUTH_STATE_COOKIE_NAME)
        if (
            payload.get("provider") != provider
            or not cookie_csrf
            or not secrets.compare_digest(str(payload.get("csrf")), cookie_csrf)
        ):
            raise ValidationError("Invalid OAuth state")

    async def _upsert_user_from_oauth(
        self,
        *,
        provider: ProviderName,
        account_id: str,
        account_email: str,
        token: dict[str, Any],
    ) -> User:
        organization = await self.org_repo.get_by_slug(settings.DEFAULT_ORGANIZATION_SLUG)
        if organization is None:
            organization = await self.org_repo.create(
                name=settings.DEFAULT_ORGANIZATION_NAME,
                slug=settings.DEFAULT_ORGANIZATION_SLUG,
            )

        account = await self.oauth_repo.get_by_provider_account(
            oauth_name=provider,
            account_id=account_id,
        )
        user = None
        if account is not None:
            user = await self.user_repo.get(account.user_id)
        if user is None:
            user = await self.user_repo.get_by_org_email(
                organization_id=organization.id,
                email=account_email,
            )
        if user is None:
            user = await self.user_repo.create(
                organization_id=organization.id,
                email=account_email,
                name=self._default_name(account_email),
                auth_provider=provider,
                provider_subject=account_id,
                role="athlete",
                is_verified=True,
            )
        else:
            user = await self.user_repo.update_oauth_identity(
                user,
                email=account_email,
                name=user.name or self._default_name(account_email),
                auth_provider=provider,
                provider_subject=account_id,
                is_verified=True,
            )

        if account is None:
            await self.oauth_repo.create(
                user_id=user.id,
                oauth_name=provider,
                access_token=token["access_token"],
                expires_at=token.get("expires_at"),
                refresh_token=token.get("refresh_token"),
                account_id=account_id,
                account_email=account_email,
            )
        else:
            await self.oauth_repo.update_tokens(
                account,
                access_token=token["access_token"],
                expires_at=token.get("expires_at"),
                refresh_token=token.get("refresh_token"),
                account_email=account_email,
            )
        return user

    @staticmethod
    def _default_name(email: str) -> str:
        local_part = email.split("@", 1)[0].replace(".", " ").replace("_", " ")
        return local_part.title() or email
