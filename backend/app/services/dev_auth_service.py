"""Local-development auth bootstrap service."""

from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import is_profile_complete
from app.auth.dev_personas import (
    DEV_USER_SPECS,
    ROLE_TARGET_KEY,
    DevAuthPersona,
    Role,
)
from app.auth.session import create_access_token
from app.core.config import Settings
from app.repositories.identity import OrganizationRepository, UserRepository

__all__ = [
    "DEV_USER_SPECS",
    "DevAuthPersona",
    "DevAuthService",
    "ROLE_TARGET_KEY",
    "Role",
]


@dataclass(frozen=True)
class SeededPrincipal:
    """Seeded local user plus a freshly minted app token."""

    key: str
    email: str
    role: Role
    user_id: UUID
    organization_id: UUID
    token: str
    next_route: str


class DevAuthService:
    """Create deterministic local users and app sessions for UI validation."""

    def __init__(
        self,
        session: AsyncSession,
        *,
        settings: Settings,
        org_repo: OrganizationRepository | None = None,
        user_repo: UserRepository | None = None,
    ) -> None:
        self.session = session
        self.settings = settings
        self.org_repo = org_repo or OrganizationRepository(session)
        self.user_repo = user_repo or UserRepository(session)

    async def seed_users(self) -> dict[str, SeededPrincipal]:
        """Create or normalize deterministic local-development users."""
        organization = await self.org_repo.get_by_slug(
            self.settings.DEFAULT_ORGANIZATION_SLUG
        )
        if organization is None:
            organization = await self.org_repo.create(
                name=self.settings.DEFAULT_ORGANIZATION_NAME,
                slug=self.settings.DEFAULT_ORGANIZATION_SLUG,
            )

        seeded: dict[str, SeededPrincipal] = {}
        for spec in DEV_USER_SPECS:
            user = await self.user_repo.get_by_org_email(
                organization_id=organization.id,
                email=spec.email,
            )
            if user is None:
                user = await self.user_repo.create(
                    organization_id=organization.id,
                    email=spec.email,
                    name=spec.name,
                    auth_provider="dev",
                    provider_subject=f"phase1-{spec.key}",
                    role=spec.role,
                    sport_team=spec.sport_team,
                )
            else:
                if user.role != spec.role or user.is_superuser != (
                    spec.role == "super_admin"
                ):
                    user = await self.user_repo.update_role(user, role=spec.role)
                if not user.is_active:
                    user = await self.user_repo.set_active(user, is_active=True)
                if user.name != spec.name or user.sport_team != spec.sport_team:
                    user = await self.user_repo.update_profile(
                        user,
                        name=spec.name,
                        sport_team=spec.sport_team,
                    )

            seeded[spec.key] = SeededPrincipal(
                key=spec.key,
                email=user.email,
                role=user.role,  # type: ignore[arg-type]
                user_id=user.id,
                organization_id=user.organization_id,
                token=create_access_token(user, self.settings),
                next_route=self._next_route(spec.key, user),
            )

        await self.session.commit()
        return seeded

    async def create_session(self, persona: DevAuthPersona) -> SeededPrincipal:
        """Create a local session principal for the requested persona."""
        seeded = await self.seed_users()
        return seeded[persona]

    @staticmethod
    def _next_route(key: str, user) -> str:
        if key in {"admin", "super_admin"}:
            return "/admin"
        return "/chat" if is_profile_complete(user) else "/profile"
