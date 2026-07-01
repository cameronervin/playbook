"""OAuth/OIDC authentication service."""

from __future__ import annotations

import secrets
from datetime import UTC, datetime, timedelta
from uuid import UUID

import jwt
import structlog
from fastapi import Request, Response
from fastapi.responses import RedirectResponse
from httpx_oauth.oauth2 import HTTPXOAuthError, OAuth2Error
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import is_profile_complete
from app.auth.dev_personas import DevAuthPersona
from app.auth.session import (
    clear_access_token_cookie,
    clear_oauth_state_cookie,
    cookie_domain,
    create_access_token,
    set_access_token_cookie,
)
from app.core.config import Settings
from app.core.exceptions import OAuthError, ValidationError
from app.infrastructure.auth import (
    OAuthIdentity,
    OAuthProviderCallbackError,
    OAuthProviderEmailMissingError,
    OAuthProviderRegistry,
    ProviderName,
)
from app.models.identity import User
from app.repositories.identity import (
    AppSessionRepository,
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

_STATE_COOKIE_MAX_AGE = 600


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


class AuthService:
    """Playbook OAuth and session orchestration."""

    def __init__(
        self,
        session: AsyncSession,
        *,
        settings: Settings,
        org_repo: OrganizationRepository | None = None,
        user_repo: UserRepository | None = None,
        oauth_repo: OAuthAccountRepository | None = None,
        app_session_repo: AppSessionRepository | None = None,
        provider_registry: OAuthProviderRegistry | None = None,
    ) -> None:
        self.session = session
        self.settings = settings
        self.org_repo = org_repo or OrganizationRepository(session)
        self.user_repo = user_repo or UserRepository(session)
        self.oauth_repo = oauth_repo or OAuthAccountRepository(session)
        self.app_session_repo = app_session_repo or AppSessionRepository(session)
        self.provider_registry = provider_registry or OAuthProviderRegistry(settings)

    def providers(self) -> AuthProvidersResponse:
        """Return enabled OAuth providers."""
        providers = [
            AuthProviderResponse(
                provider=provider.provider,
                label=provider.label,
                enabled=provider.enabled,
                login_url=provider.login_url,
            )
            for provider in self.provider_registry.list_providers()
        ]
        return AuthProvidersResponse(providers=providers)

    async def login_url(
        self,
        *,
        provider: ProviderName,
        request: Request,
        response: Response,
        persona: DevAuthPersona | None = None,
    ) -> OAuthLoginResponse:
        """Create an OAuth authorization URL and bind CSRF state in a cookie."""
        self._validate_persona(provider=provider, persona=persona)
        csrf = secrets.token_urlsafe(32)
        now = datetime.now(UTC)
        state = jwt.encode(
            {
                "provider": provider,
                "csrf": csrf,
                "iat": int(now.timestamp()),
                "exp": int((now + timedelta(seconds=_STATE_COOKIE_MAX_AGE)).timestamp()),
            },
            self.settings.OAUTH_STATE_SECRET,
            algorithm="HS256",
        )
        response.set_cookie(
            self.settings.OAUTH_STATE_COOKIE_NAME,
            csrf,
            max_age=_STATE_COOKIE_MAX_AGE,
            httponly=True,
            secure=self.settings.ENVIRONMENT.lower() in {"prod", "production"},
            samesite="lax",
            domain=cookie_domain(self.settings),
        )
        client = self.provider_registry.get_client(provider)
        authorization_url = await client.get_authorization_url(
            self._redirect_uri(provider, request),
            state=state,
            persona=persona,
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
        self._validate_state(provider=provider, state=state, request=request)
        client = self.provider_registry.get_client(provider)
        try:
            identity = await client.exchange_callback(
                code=code,
                redirect_uri=self._redirect_uri(provider, request),
            )
        except OAuthProviderCallbackError as exc:
            self._log_oauth_callback_failure(provider=provider, exc=exc)
            raise OAuthError(
                "OAuth provider callback failed",
                details={"provider": provider},
            ) from None
        except (HTTPXOAuthError, OAuth2Error) as exc:
            self._log_oauth_callback_failure(provider=provider, exc=exc)
            raise OAuthError(
                "OAuth provider callback failed",
                details={"provider": provider},
            ) from None
        except OAuthProviderEmailMissingError:
            raise OAuthError(
                "OAuth provider did not return an email address",
                details={"provider": provider},
            ) from None

        if not identity.email:
            raise OAuthError(
                "OAuth provider did not return an email address",
                details={"provider": provider},
            )

        user = await self._upsert_user_from_oauth(identity)
        expires_at = datetime.now(UTC) + timedelta(seconds=self.settings.JWT_LIFETIME_SECONDS)
        app_session = await self.app_session_repo.create(
            user_id=user.id,
            expires_at=expires_at,
        )
        await self.session.commit()
        access_token = create_access_token(
            user,
            self.settings,
            session_id=app_session.id,
            expires_at=app_session.expires_at,
        )
        set_access_token_cookie(response, access_token, self.settings)
        clear_oauth_state_cookie(response, self.settings)
        logger.info(
            "auth_oauth_login_succeeded",
            provider=provider,
            user_id=str(user.id),
            organization_id=str(user.organization_id),
        )
        return SessionResponse(
            user=user_to_response(user),
            access_token=access_token,
            next_route=self._next_route(user=user),
        )

    def browser_redirect_response(self, session: SessionResponse) -> RedirectResponse:
        """Build a browser redirect response with session cookies attached."""
        redirect = RedirectResponse(
            url=f"{self.settings.FRONTEND_URL.rstrip('/')}{session.next_route}",
            status_code=303,
        )
        set_access_token_cookie(redirect, session.access_token, self.settings)
        clear_oauth_state_cookie(redirect, self.settings)
        return redirect

    async def logout(self, request: Request, response: Response) -> None:
        """Revoke the current app session when present and clear its cookie."""
        if session_id := self._session_id_from_request(request):
            app_session = await self.app_session_repo.get(session_id)
            if app_session is not None and app_session.revoked_at is None:
                await self.app_session_repo.revoke(
                    app_session,
                    revoked_at=datetime.now(UTC),
                    reason="logout",
                )
                await self.session.commit()
                logger.info("auth_session_revoked", session_id=str(app_session.id))
        clear_access_token_cookie(response, self.settings)

    @staticmethod
    def _validate_persona(
        *,
        provider: ProviderName,
        persona: DevAuthPersona | None,
    ) -> None:
        if provider != "dev" and persona is not None:
            raise ValidationError(
                "Dev persona is only supported for Developer SSO",
                details={"provider": provider},
            )

    def _redirect_uri(self, provider: ProviderName, request: Request) -> str:
        base_url = self.settings.API_PUBLIC_URL.rstrip("/")
        if base_url:
            return f"{base_url}/api/v1/auth/{provider}/callback"
        return str(request.base_url).rstrip("/") + f"/api/v1/auth/{provider}/callback"

    def _session_id_from_request(self, request: Request) -> UUID | None:
        token = request.cookies.get(self.settings.ACCESS_TOKEN_COOKIE_NAME)
        if not token:
            authorization = request.headers.get("Authorization", "")
            scheme, _, credentials = authorization.partition(" ")
            if scheme.lower() == "bearer" and credentials:
                token = credentials
        if not token:
            return None
        try:
            payload = jwt.decode(
                token,
                self.settings.SECRET_KEY,
                algorithms=["HS256"],
                options={"verify_exp": False},
            )
            return UUID(str(payload.get("sid")))
        except (TypeError, ValueError, jwt.PyJWTError):
            return None

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
                self.settings.OAUTH_STATE_SECRET,
                algorithms=["HS256"],
            )
        except jwt.PyJWTError as exc:
            raise ValidationError("Invalid OAuth state") from exc

        cookie_csrf = request.cookies.get(self.settings.OAUTH_STATE_COOKIE_NAME)
        if (
            payload.get("provider") != provider
            or not cookie_csrf
            or not secrets.compare_digest(str(payload.get("csrf")), cookie_csrf)
        ):
            raise ValidationError("Invalid OAuth state")

    async def _upsert_user_from_oauth(self, identity: OAuthIdentity) -> User:
        organization = await self.org_repo.get_by_slug(
            self.settings.DEFAULT_ORGANIZATION_SLUG
        )
        if organization is None:
            organization = await self.org_repo.create(
                name=self.settings.DEFAULT_ORGANIZATION_NAME,
                slug=self.settings.DEFAULT_ORGANIZATION_SLUG,
            )

        account = await self.oauth_repo.get_by_provider_account(
            oauth_name=identity.provider,
            account_id=identity.subject,
        )
        user = None
        if account is not None:
            user = await self.user_repo.get(account.user_id)
        if user is None:
            user = await self.user_repo.get_by_org_email(
                organization_id=organization.id,
                email=identity.email,
            )
        if account is None and user is not None:
            account = await self.oauth_repo.get_by_user_provider(
                user_id=user.id,
                oauth_name=identity.provider,
            )
        if user is None:
            user = await self.user_repo.create(
                organization_id=organization.id,
                email=identity.email,
                name=identity.name or self._default_name(identity.email),
                auth_provider=identity.provider,
                provider_subject=identity.subject,
                role=identity.role or "athlete",
                sport_team=identity.sport_team,
                is_verified=True,
            )
        else:
            user = await self.user_repo.update_oauth_identity(
                user,
                email=identity.email,
                name=self._resolved_name(user, identity),
                auth_provider=identity.provider,
                provider_subject=identity.subject,
                is_verified=True,
            )
            if identity.role is not None and user.role != identity.role:
                user = await self.user_repo.update_role(user, role=identity.role)
            if not user.is_active:
                user = await self.user_repo.set_active(user, is_active=True)
            if identity.provider == "dev" and (
                user.name != identity.name or user.sport_team != identity.sport_team
            ):
                user = await self.user_repo.update_profile(
                    user,
                    name=identity.name or self._default_name(identity.email),
                    sport_team=identity.sport_team,
                )

        if account is None:
            await self.oauth_repo.create(
                user_id=user.id,
                oauth_name=identity.provider,
                access_token=identity.access_token,
                expires_at=identity.expires_at,
                refresh_token=identity.refresh_token,
                account_id=identity.subject,
                account_email=identity.email,
            )
        else:
            await self.oauth_repo.update_tokens(
                account,
                access_token=identity.access_token,
                expires_at=identity.expires_at,
                refresh_token=identity.refresh_token,
                account_id=identity.subject,
                account_email=identity.email,
            )
        return user

    def _next_route(self, *, user: User) -> str:
        if user.role in {"admin", "super_admin"}:
            return "/admin"
        return "/chat" if is_profile_complete(user) else "/profile"

    def _resolved_name(self, user: User, identity: OAuthIdentity) -> str:
        if identity.provider == "dev" and identity.name:
            return identity.name
        if identity.name and self._should_replace_name_from_provider(user, identity):
            return identity.name
        return user.name or identity.name or self._default_name(identity.email)

    def _should_replace_name_from_provider(self, user: User, identity: OAuthIdentity) -> bool:
        if not user.name:
            return True
        return user.name in {
            self._default_name(user.email),
            self._default_name(identity.email),
        }

    @staticmethod
    def _log_oauth_callback_failure(
        *,
        provider: ProviderName,
        exc: Exception,
    ) -> None:
        logger.warning(
            "auth_oauth_provider_callback_failed",
            provider=provider,
            phase=getattr(exc, "phase", "callback"),
            error_type=getattr(exc, "error_type", type(exc).__name__),
            status_code=getattr(exc, "status_code", None),
        )

    @staticmethod
    def _default_name(email: str) -> str:
        local_part = email.split("@", 1)[0].replace(".", " ").replace("_", " ")
        return local_part.title() or email
