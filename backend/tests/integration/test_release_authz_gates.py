"""Release-gate coverage for production auth and role boundaries."""

from __future__ import annotations

import pytest

from app.repositories.identity import OrganizationRepository, UserRepository


@pytest.mark.asyncio
async def test_release_authz_rejects_unauthenticated_workspace_routes(route_client) -> None:
    for path in (
        "/api/v1/users/me",
        "/api/v1/conversations",
        "/api/v1/admin/analytics/summary",
        "/api/v1/admin/users",
    ):
        response = await route_client.client.get(path)

        assert response.status_code == 401, path


@pytest.mark.asyncio
async def test_release_authz_rejects_athlete_access_to_admin_apis(
    route_client,
    db_session,
) -> None:
    organization = await OrganizationRepository(db_session).create(
        name="Playbook Athletics",
        slug="playbook",
    )
    athlete = await UserRepository(db_session).create(
        organization_id=organization.id,
        email="athlete@example.com",
        name="Jordan Athlete",
        auth_provider="google",
        provider_subject="athlete-subject",
        role="athlete",
    )
    route_client.authenticate_as(athlete)

    analytics_response = await route_client.client.get(
        "/api/v1/admin/analytics/summary",
        headers={"X-Request-ID": "req-admin-boundary"},
    )
    users_response = await route_client.client.get(
        "/api/v1/admin/users",
        headers={"X-Request-ID": "req-super-boundary"},
    )

    assert analytics_response.status_code == 403
    assert analytics_response.json()["error"]["message"] == "Admin role required"
    assert users_response.status_code == 403
    assert users_response.json()["error"]["message"] == "Super admin role required"


@pytest.mark.asyncio
async def test_release_authz_rejects_admin_super_admin_actions(
    route_client,
    db_session,
) -> None:
    organization = await OrganizationRepository(db_session).create(
        name="Playbook Athletics",
        slug="playbook",
    )
    user_repo = UserRepository(db_session)
    admin = await user_repo.create(
        organization_id=organization.id,
        email="admin@example.com",
        name="Admin User",
        auth_provider="google",
        provider_subject="admin-subject",
        role="admin",
    )
    target = await user_repo.create(
        organization_id=organization.id,
        email="athlete@example.com",
        name="Jordan Athlete",
        auth_provider="google",
        provider_subject="athlete-subject",
        role="athlete",
    )
    route_client.authenticate_as(admin)

    response = await route_client.client.patch(
        f"/api/v1/admin/users/{target.id}/role",
        headers={"X-Request-ID": "req-super-mutation"},
        json={"role": "super_admin"},
    )

    assert response.status_code == 403
    assert response.json()["error"] == {
        "code": "FORBIDDEN",
        "message": "Super admin role required",
        "retryable": False,
        "details": {"request_id": "req-super-mutation"},
    }
