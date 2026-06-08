"""Tests for Playbook auth and role dependencies."""

from uuid import uuid4

import jwt
import pytest
from fastapi import HTTPException

from app.auth.dependencies import (
    current_active_user,
    is_profile_complete,
    require_admin,
    require_athlete,
    require_super_admin,
)
from app.core.config import settings
from app.models.identity import User
from app.repositories.identity import OrganizationRepository, UserRepository


def _token(user_id: str) -> str:
    return jwt.encode({"sub": user_id}, settings.SECRET_KEY, algorithm="HS256")


@pytest.mark.asyncio
async def test_current_active_user_loads_db_user(db_session) -> None:
    repo = UserRepository(db_session)
    organization = await OrganizationRepository(db_session).create(
        name="Playbook Athletics",
        slug="playbook-auth-test",
    )
    user = await repo.create(
        organization_id=organization.id,
        email="athlete@example.com",
        name="Jordan Athlete",
        auth_provider="google",
        provider_subject="google-sub",
    )

    loaded = await current_active_user(token=_token(str(user.id)), session=db_session)

    assert loaded is user


@pytest.mark.asyncio
async def test_current_active_user_rejects_missing_invalid_and_inactive_user(
    db_session,
) -> None:
    repo = UserRepository(db_session)
    organization = await OrganizationRepository(db_session).create(
        name="Playbook Athletics",
        slug="playbook-inactive-test",
    )
    inactive = await repo.create(
        organization_id=organization.id,
        email="inactive@example.com",
        name="Inactive User",
        auth_provider="google",
        provider_subject="inactive-sub",
        is_active=False,
    )

    with pytest.raises(HTTPException) as missing:
        await current_active_user(token=None, session=db_session)
    with pytest.raises(HTTPException) as invalid:
        await current_active_user(token="not-a-token", session=db_session)
    with pytest.raises(HTTPException) as inactive_error:
        await current_active_user(token=_token(str(inactive.id)), session=db_session)

    assert missing.value.status_code == 401
    assert invalid.value.status_code == 401
    assert inactive_error.value.status_code == 401


def test_role_dependencies_and_profile_completion() -> None:
    athlete = User(
        id=uuid4(),
        organization_id=uuid4(),
        email="athlete@example.com",
        name="Jordan Athlete",
        role="athlete",
        auth_provider="google",
        provider_subject="google-sub",
        sport_team="Basketball",
        is_active=True,
    )
    admin = User(
        id=uuid4(),
        organization_id=uuid4(),
        email="admin@example.com",
        name="Admin User",
        role="admin",
        auth_provider="google",
        provider_subject="admin-sub",
        is_active=True,
    )
    super_admin = User(
        id=uuid4(),
        organization_id=uuid4(),
        email="super@example.com",
        name="Super Admin",
        role="super_admin",
        auth_provider="google",
        provider_subject="super-sub",
        is_active=True,
    )

    assert require_athlete(athlete) is athlete
    assert require_admin(admin) is admin
    assert require_admin(super_admin) is super_admin
    assert require_super_admin(super_admin) is super_admin
    assert is_profile_complete(athlete) is True
    assert is_profile_complete(admin) is True

    with pytest.raises(HTTPException) as athlete_as_admin:
        require_admin(athlete)
    with pytest.raises(HTTPException) as admin_as_super:
        require_super_admin(admin)

    assert athlete_as_admin.value.status_code == 403
    assert admin_as_super.value.status_code == 403
