"""Integration coverage for Phase 1 manual validation auth seeding."""

from __future__ import annotations

import jwt

from app.auth.dependencies import is_profile_complete
from app.repositories.identity import UserRepository
from scripts.phase1_dev_auth import ROLE_TARGET_KEY, seed_phase1_users


async def test_seed_phase1_users_creates_reusable_principals(
    db_session,
    test_settings,
) -> None:
    """Seed helper creates local users and returns valid app JWTs."""
    seeded = await seed_phase1_users(db_session, test_settings)

    assert {"athlete", "new_athlete", "admin", "super_admin", ROLE_TARGET_KEY} == set(
        seeded
    )
    assert seeded["athlete"].role == "athlete"
    assert seeded["new_athlete"].role == "athlete"
    assert seeded["admin"].role == "admin"
    assert seeded["super_admin"].role == "super_admin"
    assert seeded[ROLE_TARGET_KEY].email == "role-target@example.com"
    assert seeded[ROLE_TARGET_KEY].role == "athlete"

    payload = jwt.decode(
        seeded["athlete"].token,
        test_settings.SECRET_KEY,
        algorithms=["HS256"],
    )
    assert payload["sub"] == str(seeded["athlete"].user_id)

    new_athlete = await UserRepository(db_session).get(seeded["new_athlete"].user_id)
    assert new_athlete is not None
    assert not is_profile_complete(new_athlete)

    role_target = await UserRepository(db_session).get(seeded[ROLE_TARGET_KEY].user_id)
    assert role_target is not None
    await UserRepository(db_session).update_role(role_target, role="admin")
    await db_session.commit()

    reseeded = await seed_phase1_users(db_session, test_settings)

    assert reseeded[ROLE_TARGET_KEY].user_id == seeded[ROLE_TARGET_KEY].user_id
    assert reseeded[ROLE_TARGET_KEY].role == "athlete"
