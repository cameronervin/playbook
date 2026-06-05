"""Integration tests for Playbook identity repositories."""

from uuid import uuid4

import pytest
from sqlalchemy import select

from app.models.identity import User
from app.repositories.identity import OrganizationRepository, UserRepository


@pytest.mark.asyncio
async def test_organization_repository_creates_and_gets_organization(db_session):
    repo = OrganizationRepository(db_session)

    organization = await repo.create(name="Playbook Athletics", slug="playbook")

    assert organization.id is not None
    assert organization.theme_config == {}

    by_id = await repo.get(organization.id)
    by_slug = await repo.get_by_slug("playbook")
    organizations = await repo.list_active()

    assert by_id is organization
    assert by_slug is organization
    assert organizations == [organization]


@pytest.mark.asyncio
async def test_user_repository_supports_identity_profile_role_and_org_listing(
    db_session,
):
    org_repo = OrganizationRepository(db_session)
    user_repo = UserRepository(db_session)
    organization = await org_repo.create(name="Playbook Athletics", slug="playbook")
    other_organization = await org_repo.create(name="Other Athletics", slug="other")

    user = await user_repo.create(
        organization_id=organization.id,
        email="athlete@example.com",
        name="Jordan Athlete",
        auth_provider="google",
        provider_subject="google-subject-1",
    )
    await user_repo.create(
        organization_id=other_organization.id,
        email="athlete@example.com",
        name="Other Athlete",
        auth_provider="microsoft",
        provider_subject="microsoft-subject-1",
    )

    by_id = await user_repo.get(user.id)
    by_email = await user_repo.get_by_org_email(
        organization_id=organization.id,
        email="athlete@example.com",
    )
    by_provider = await user_repo.get_by_provider_subject(
        auth_provider="google",
        provider_subject="google-subject-1",
    )

    assert by_id is user
    assert by_email is user
    assert by_provider is user

    updated_profile = await user_repo.update_profile(
        user,
        name="Jordan Updated",
        sport_team="Basketball",
    )
    updated_role = await user_repo.update_role(user, role="admin")
    users = await user_repo.list_by_organization(organization.id)
    active_users = await user_repo.list_by_organization(
        organization.id,
        active_only=True,
    )

    assert updated_profile.name == "Jordan Updated"
    assert updated_profile.sport_team == "Basketball"
    assert updated_role.role == "admin"
    assert users == [user]
    assert active_users == [user]

    persisted_user = await db_session.scalar(select(User).where(User.id == user.id))
    assert persisted_user is user


@pytest.mark.asyncio
async def test_user_repository_returns_none_for_missing_records(db_session):
    repo = UserRepository(db_session)

    assert await repo.get(uuid4()) is None
    assert (
        await repo.get_by_provider_subject(
            auth_provider="google",
            provider_subject="missing",
        )
        is None
    )
