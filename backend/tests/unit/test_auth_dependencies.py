"""Tests for Playbook auth and role dependencies."""

from datetime import UTC, datetime, timedelta
from uuid import uuid4

import jwt
import pytest
from fastapi import HTTPException
from starlette.requests import Request

from app.auth.dependencies import (
    current_active_user,
    is_profile_complete,
    require_admin,
    require_athlete,
    require_super_admin,
)
from app.core.config import Settings
from app.core.exceptions import UnauthorizedError
from app.models.identity import User
from app.repositories.identity import AppSessionRepository, OrganizationRepository, UserRepository


def _request() -> Request:
    return Request({"type": "http", "method": "GET", "path": "/", "headers": []})


def _token(user_id: str, session_id: str, settings: Settings) -> str:
    now = datetime.now(UTC)
    return jwt.encode(
        {
            "sub": user_id,
            "sid": session_id,
            "iat": int(now.timestamp()),
            "exp": int((now + timedelta(hours=1)).timestamp()),
        },
        settings.SECRET_KEY,
        algorithm="HS256",
    )


@pytest.mark.asyncio
async def test_current_active_user_loads_db_user(db_session, test_settings) -> None:
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
    app_session = await AppSessionRepository(db_session).create(
        user_id=user.id,
        expires_at=datetime.now(UTC) + timedelta(hours=1),
    )

    loaded = await current_active_user(
        token=_token(str(user.id), str(app_session.id), test_settings),
        session=db_session,
        settings=test_settings,
        request=_request(),
    )

    assert loaded is user


@pytest.mark.asyncio
async def test_current_active_user_rejects_missing_invalid_and_inactive_user(
    db_session,
    test_settings,
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

    with pytest.raises(UnauthorizedError) as missing:
        await current_active_user(
            token=None,
            session=db_session,
            settings=test_settings,
            request=_request(),
        )
    with pytest.raises(UnauthorizedError) as invalid:
        await current_active_user(
            token="not-a-token",
            session=db_session,
            settings=test_settings,
            request=_request(),
        )
    with pytest.raises(HTTPException) as inactive_error:
        inactive_session = await AppSessionRepository(db_session).create(
            user_id=inactive.id,
            expires_at=datetime.now(UTC) + timedelta(hours=1),
        )
        await current_active_user(
            token=_token(str(inactive.id), str(inactive_session.id), test_settings),
            session=db_session,
            settings=test_settings,
            request=_request(),
        )

    assert missing.value.status == 401
    assert invalid.value.status == 401
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
