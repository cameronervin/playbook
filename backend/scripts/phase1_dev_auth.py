"""Seed local Phase 1 validation users and mint app JWTs.

This module is intentionally local-development tooling. It creates throwaway
users in the configured backend database so Swagger and curl can exercise
role-protected endpoints without requiring real OAuth providers.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import shlex
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Literal
from uuid import UUID

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from sqlalchemy.ext.asyncio import AsyncSession  # noqa: E402

from app.core.config import settings  # noqa: E402
from app.infrastructure.db.session import (  # noqa: E402
    cleanup_db_engine,
    get_session_factory,
)
from app.repositories.identity import (  # noqa: E402
    OrganizationRepository,
    UserRepository,
)
from app.services.auth_service import create_access_token  # noqa: E402

Role = Literal["athlete", "admin", "super_admin"]
ROLE_TARGET_KEY = "role_target"


@dataclass(frozen=True)
class Phase1UserSpec:
    """Input spec for one throwaway local validation user."""

    key: str
    email: str
    name: str
    role: Role
    sport_team: str | None = None


@dataclass(frozen=True)
class SeededPrincipal:
    """Seeded local user plus a freshly minted app token."""

    key: str
    email: str
    role: Role
    user_id: UUID
    token: str


PHASE1_USER_SPECS: tuple[Phase1UserSpec, ...] = (
    Phase1UserSpec(
        key="athlete",
        email="phase1-athlete@example.com",
        name="Phase 1 Athlete",
        role="athlete",
        sport_team="Basketball",
    ),
    Phase1UserSpec(
        key="admin",
        email="phase1-admin@example.com",
        name="Phase 1 Admin",
        role="admin",
    ),
    Phase1UserSpec(
        key="super_admin",
        email="phase1-super@example.com",
        name="Phase 1 Super Admin",
        role="super_admin",
    ),
    Phase1UserSpec(
        key=ROLE_TARGET_KEY,
        email="role-target@example.com",
        name="Role Target",
        role="athlete",
        sport_team="Soccer",
    ),
)


async def seed_phase1_users(
    session: AsyncSession,
) -> dict[str, SeededPrincipal]:
    """Create or normalize throwaway users used by manual endpoint validation."""
    org_repo = OrganizationRepository(session)
    user_repo = UserRepository(session)

    organization = await org_repo.get_by_slug(settings.DEFAULT_ORGANIZATION_SLUG)
    if organization is None:
        organization = await org_repo.create(
            name=settings.DEFAULT_ORGANIZATION_NAME,
            slug=settings.DEFAULT_ORGANIZATION_SLUG,
        )

    seeded: dict[str, SeededPrincipal] = {}
    for spec in PHASE1_USER_SPECS:
        user = await user_repo.get_by_org_email(
            organization_id=organization.id,
            email=spec.email,
        )
        if user is None:
            user = await user_repo.create(
                organization_id=organization.id,
                email=spec.email,
                name=spec.name,
                auth_provider="dev",
                provider_subject=f"phase1-{spec.key}",
                role=spec.role,
                sport_team=spec.sport_team,
            )
        else:
            needs_role_sync = user.role != spec.role or user.is_superuser != (
                spec.role == "super_admin"
            )
            if needs_role_sync:
                user = await user_repo.update_role(user, role=spec.role)
            if not user.is_active:
                user = await user_repo.set_active(user, is_active=True)
            if spec.sport_team is not None and (
                user.name != spec.name or user.sport_team != spec.sport_team
            ):
                user = await user_repo.update_profile(
                    user,
                    name=spec.name,
                    sport_team=spec.sport_team,
                )

        seeded[spec.key] = SeededPrincipal(
            key=spec.key,
            email=user.email,
            role=user.role,  # type: ignore[arg-type]
            user_id=user.id,
            token=create_access_token(user),
        )

    await session.commit()
    return seeded


def render_shell_exports(seeded: dict[str, SeededPrincipal]) -> str:
    """Render shell exports consumable by eval/source."""
    athlete = seeded["athlete"]
    admin = seeded["admin"]
    super_admin = seeded["super_admin"]
    role_target = seeded[ROLE_TARGET_KEY]
    exports = {
        "ATHLETE_TOKEN": athlete.token,
        "ADMIN_TOKEN": admin.token,
        "SUPER_TOKEN": super_admin.token,
        "ROLE_TARGET_ID": str(role_target.user_id),
        "ROLE_TARGET_EMAIL": role_target.email,
    }
    return "\n".join(
        f"export {name}={shlex.quote(value)}" for name, value in exports.items()
    )


def render_json(seeded: dict[str, SeededPrincipal]) -> str:
    """Render seeded principals as JSON for inspection or automation."""
    payload = {
        key: {
            "email": principal.email,
            "role": principal.role,
            "user_id": str(principal.user_id),
            "token": principal.token,
        }
        for key, principal in seeded.items()
    }
    return json.dumps(payload, indent=2, sort_keys=True)


async def _run(format_name: Literal["shell", "json"]) -> str:
    async with get_session_factory()() as session:
        seeded = await seed_phase1_users(session)
    await cleanup_db_engine()
    if format_name == "json":
        return render_json(seeded)
    return render_shell_exports(seeded)


def main() -> None:
    """CLI entrypoint."""
    parser = argparse.ArgumentParser(
        description="Seed Phase 1 local validation users and print app JWT exports.",
    )
    parser.add_argument(
        "--format",
        choices=("shell", "json"),
        default="shell",
        help="Output format. Use shell with eval, or json for inspection.",
    )
    args = parser.parse_args()
    print(asyncio.run(_run(args.format)))


if __name__ == "__main__":
    main()
