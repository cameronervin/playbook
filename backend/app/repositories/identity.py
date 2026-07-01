"""Repositories for organization and user identity data."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any
from uuid import UUID

from fastapi import Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.infrastructure.db.session import get_db
from app.models.identity import AppSession, OAuthAccount, Organization, User


class OrganizationRepository:
    """Data access for Playbook organizations."""

    def __init__(self, session: AsyncSession = Depends(get_db)) -> None:
        self.session = session

    async def get(self, organization_id: UUID) -> Organization | None:
        """Return an organization by ID."""
        result = await self.session.execute(
            select(Organization).where(Organization.id == organization_id)
        )
        return result.scalar_one_or_none()

    async def get_by_slug(self, slug: str) -> Organization | None:
        """Return an organization by slug."""
        result = await self.session.execute(
            select(Organization).where(Organization.slug == slug)
        )
        return result.scalar_one_or_none()

    async def list_active(
        self,
        *,
        limit: int = 100,
        offset: int = 0,
    ) -> list[Organization]:
        """Return active organizations ordered by creation date."""
        result = await self.session.scalars(
            select(Organization)
            .where(Organization.is_active.is_(True))
            .order_by(Organization.created_at.desc(), Organization.id.asc())
            .limit(limit)
            .offset(offset)
        )
        return list(result.all())

    async def create(
        self,
        *,
        name: str,
        slug: str,
        theme_config: dict[str, Any] | None = None,
        is_active: bool = True,
    ) -> Organization:
        """Create an organization without committing the transaction."""
        organization = Organization(name=name, slug=slug, is_active=is_active)
        if theme_config is not None:
            organization.theme_config = theme_config

        self.session.add(organization)
        await self.session.flush()
        await self.session.refresh(organization)
        return organization


class UserRepository:
    """Data access for Playbook user profiles and roles."""

    def __init__(self, session: AsyncSession = Depends(get_db)) -> None:
        self.session = session

    async def get(self, user_id: UUID) -> User | None:
        """Return a user by ID."""
        result = await self.session.execute(select(User).where(User.id == user_id))
        return result.scalar_one_or_none()

    async def get_by_org_email(
        self,
        *,
        organization_id: UUID,
        email: str,
        active_only: bool = False,
    ) -> User | None:
        """Return a user by organization and email."""
        stmt = select(User).where(
            User.organization_id == organization_id,
            User.email == email,
        )
        if active_only:
            stmt = stmt.where(User.is_active.is_(True))

        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_by_provider_subject(
        self,
        *,
        auth_provider: str,
        provider_subject: str,
        active_only: bool = False,
    ) -> User | None:
        """Return a user by OAuth/OIDC provider subject."""
        stmt = select(User).where(
            User.auth_provider == auth_provider,
            User.provider_subject == provider_subject,
        )
        if active_only:
            stmt = stmt.where(User.is_active.is_(True))

        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def list_by_organization(
        self,
        organization_id: UUID,
        *,
        active_only: bool = False,
        role: str | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> list[User]:
        """Return users scoped to an organization."""
        stmt = select(User).where(User.organization_id == organization_id)
        if active_only:
            stmt = stmt.where(User.is_active.is_(True))
        if role is not None:
            stmt = stmt.where(User.role == role)

        result = await self.session.scalars(
            stmt.order_by(User.created_at.desc(), User.id.asc()).limit(limit).offset(offset)
        )
        return list(result.all())

    async def create(
        self,
        *,
        organization_id: UUID,
        email: str,
        name: str,
        auth_provider: str,
        provider_subject: str,
        role: str = "athlete",
        sport_team: str | None = None,
        hashed_password: str = "",
        is_verified: bool = True,
        is_superuser: bool | None = None,
        is_active: bool = True,
    ) -> User:
        """Create a local Playbook user without committing the transaction."""
        resolved_is_superuser = role == "super_admin" if is_superuser is None else is_superuser
        user = User(
            organization_id=organization_id,
            email=email,
            name=name,
            role=role,
            auth_provider=auth_provider,
            provider_subject=provider_subject,
            hashed_password=hashed_password,
            sport_team=sport_team,
            is_active=is_active,
            is_verified=is_verified,
            is_superuser=resolved_is_superuser,
        )
        self.session.add(user)
        await self.session.flush()
        await self.session.refresh(user)
        return user

    async def update_profile(
        self,
        user: User,
        *,
        name: str,
        sport_team: str | None,
    ) -> User:
        """Update athlete profile fields without committing the transaction."""
        user.name = name
        user.sport_team = sport_team
        await self.session.flush()
        await self.session.refresh(user)
        return user

    async def update_oauth_identity(
        self,
        user: User,
        *,
        email: str,
        name: str,
        auth_provider: str,
        provider_subject: str,
        is_verified: bool = True,
    ) -> User:
        """Update OAuth identity fields without committing the transaction."""
        user.email = email
        user.name = name
        user.auth_provider = auth_provider
        user.provider_subject = provider_subject
        user.is_verified = is_verified
        await self.session.flush()
        await self.session.refresh(user)
        return user

    async def update_role(self, user: User, *, role: str) -> User:
        """Update a user's role without committing the transaction."""
        user.role = role
        user.is_superuser = role == "super_admin"
        await self.session.flush()
        await self.session.refresh(user)
        return user

    async def set_active(self, user: User, *, is_active: bool) -> User:
        """Update active status without committing the transaction."""
        user.is_active = is_active
        await self.session.flush()
        await self.session.refresh(user)
        return user


class AppSessionRepository:
    """Data access for server-side application sessions."""

    def __init__(self, session: AsyncSession = Depends(get_db)) -> None:
        self.session = session

    async def get(self, session_id: UUID) -> AppSession | None:
        """Return an app session by ID."""
        result = await self.session.execute(
            select(AppSession).where(AppSession.id == session_id)
        )
        return result.scalar_one_or_none()

    async def create(
        self,
        *,
        user_id: UUID,
        expires_at: datetime,
        last_seen_at: datetime | None = None,
    ) -> AppSession:
        """Create an app session without committing the transaction."""
        now = datetime.now(UTC)
        app_session = AppSession(
            user_id=user_id,
            last_seen_at=last_seen_at or now,
            expires_at=expires_at,
        )
        self.session.add(app_session)
        await self.session.flush()
        await self.session.refresh(app_session)
        return app_session

    async def touch(
        self,
        app_session: AppSession,
        *,
        last_seen_at: datetime,
        expires_at: datetime | None = None,
    ) -> AppSession:
        """Update session activity timestamps without committing."""
        app_session.last_seen_at = last_seen_at
        if expires_at is not None:
            app_session.expires_at = expires_at
        await self.session.flush()
        await self.session.refresh(app_session)
        return app_session

    async def revoke(
        self,
        app_session: AppSession,
        *,
        revoked_at: datetime,
        reason: str,
    ) -> AppSession:
        """Mark an app session revoked without committing."""
        app_session.revoked_at = revoked_at
        app_session.revoked_reason = reason
        await self.session.flush()
        await self.session.refresh(app_session)
        return app_session


class OAuthAccountRepository:
    """Data access for OAuth accounts linked to Playbook users."""

    def __init__(self, session: AsyncSession = Depends(get_db)) -> None:
        self.session = session

    async def get_by_provider_account(
        self,
        *,
        oauth_name: str,
        account_id: str,
    ) -> OAuthAccount | None:
        """Return an OAuth account by provider and provider subject."""
        result = await self.session.execute(
            select(OAuthAccount).where(
                OAuthAccount.oauth_name == oauth_name,
                OAuthAccount.account_id == account_id,
            )
        )
        return result.scalar_one_or_none()

    async def get_by_user_provider(
        self,
        *,
        user_id: UUID,
        oauth_name: str,
    ) -> OAuthAccount | None:
        """Return an OAuth account for a user and provider."""
        result = await self.session.execute(
            select(OAuthAccount).where(
                OAuthAccount.user_id == user_id,
                OAuthAccount.oauth_name == oauth_name,
            )
        )
        return result.scalar_one_or_none()

    async def create(
        self,
        *,
        user_id: UUID,
        oauth_name: str,
        access_token: str,
        account_id: str,
        account_email: str,
        expires_at: int | None = None,
        refresh_token: str | None = None,
    ) -> OAuthAccount:
        """Create an OAuth account without committing the transaction."""
        account = OAuthAccount(
            user_id=user_id,
            oauth_name=oauth_name,
            access_token=access_token,
            expires_at=expires_at,
            refresh_token=refresh_token,
            account_id=account_id,
            account_email=account_email,
        )
        self.session.add(account)
        await self.session.flush()
        await self.session.refresh(account)
        return account

    async def update_tokens(
        self,
        account: OAuthAccount,
        *,
        access_token: str,
        account_email: str,
        expires_at: int | None = None,
        refresh_token: str | None = None,
        account_id: str | None = None,
    ) -> OAuthAccount:
        """Update OAuth account identity and token metadata without committing."""
        if account_id is not None:
            account.account_id = account_id
        account.access_token = access_token
        account.account_email = account_email
        account.expires_at = expires_at
        account.refresh_token = refresh_token
        await self.session.flush()
        await self.session.refresh(account)
        return account
