"""Repositories for organization and user identity data."""

from __future__ import annotations

from typing import Any
from uuid import UUID

from fastapi import Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.infrastructure.db.session import get_db
from app.models.identity import Organization, User


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
        is_active: bool = True,
    ) -> User:
        """Create a local Playbook user without committing the transaction."""
        user = User(
            organization_id=organization_id,
            email=email,
            name=name,
            role=role,
            auth_provider=auth_provider,
            provider_subject=provider_subject,
            sport_team=sport_team,
            is_active=is_active,
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
        sport_team: str,
    ) -> User:
        """Update athlete profile fields without committing the transaction."""
        user.name = name
        user.sport_team = sport_team
        await self.session.flush()
        await self.session.refresh(user)
        return user

    async def update_role(self, user: User, *, role: str) -> User:
        """Update a user's role without committing the transaction."""
        user.role = role
        await self.session.flush()
        await self.session.refresh(user)
        return user

    async def set_active(self, user: User, *, is_active: bool) -> User:
        """Update active status without committing the transaction."""
        user.is_active = is_active
        await self.session.flush()
        await self.session.refresh(user)
        return user
