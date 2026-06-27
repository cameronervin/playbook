"""Deterministic local-development auth personas."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

DevAuthPersona = Literal["athlete", "new_athlete", "admin", "super_admin"]
Role = Literal["athlete", "admin", "super_admin"]
ROLE_TARGET_KEY = "role_target"


@dataclass(frozen=True)
class DevUserSpec:
    """Input spec for one deterministic local-development user."""

    key: str
    email: str
    name: str
    role: Role
    sport_team: str | None = None


DEV_USER_SPECS: tuple[DevUserSpec, ...] = (
    DevUserSpec(
        key="athlete",
        email="phase1-athlete@example.com",
        name="Phase 1 Athlete",
        role="athlete",
        sport_team="Basketball",
    ),
    DevUserSpec(
        key="new_athlete",
        email="phase1-new-athlete@example.com",
        name="Phase 1 New Athlete",
        role="athlete",
    ),
    DevUserSpec(
        key="admin",
        email="phase1-admin@example.com",
        name="Phase 1 Admin",
        role="admin",
    ),
    DevUserSpec(
        key="super_admin",
        email="phase1-super@example.com",
        name="Phase 1 Super Admin",
        role="super_admin",
    ),
    DevUserSpec(
        key=ROLE_TARGET_KEY,
        email="role-target@example.com",
        name="Role Target",
        role="athlete",
        sport_team="Soccer",
    ),
)


def get_dev_user_spec(persona: DevAuthPersona) -> DevUserSpec:
    """Return the deterministic local user spec for a browser persona."""
    for spec in DEV_USER_SPECS:
        if spec.key == persona:
            return spec
    raise ValueError(f"Unknown development auth persona: {persona}")
