"""Route-level tests for super-admin user-management endpoints."""

from __future__ import annotations

import pytest
from sqlalchemy import select

from app.models.audit import AuditLog
from app.repositories.identity import OrganizationRepository, UserRepository


@pytest.mark.asyncio
async def test_super_admin_lists_users_with_role_filter(route_client, db_session) -> None:
    organization = await OrganizationRepository(db_session).create(
        name="Playbook Athletics",
        slug="playbook",
    )
    user_repo = UserRepository(db_session)
    super_admin = await user_repo.create(
        organization_id=organization.id,
        email="super@example.com",
        name="Super Admin",
        auth_provider="google",
        provider_subject="super-subject",
        role="super_admin",
    )
    athlete = await user_repo.create(
        organization_id=organization.id,
        email="athlete@example.com",
        name="Jordan Athlete",
        auth_provider="google",
        provider_subject="athlete-subject",
        role="athlete",
    )
    await user_repo.create(
        organization_id=organization.id,
        email="admin@example.com",
        name="Admin User",
        auth_provider="google",
        provider_subject="admin-subject",
        role="admin",
    )
    route_client.authenticate_as(super_admin)

    response = await route_client.client.get(
        "/api/v1/admin/users",
        params={"role": "athlete"},
    )

    assert response.status_code == 200
    assert [user["id"] for user in response.json()] == [str(athlete.id)]


@pytest.mark.asyncio
async def test_super_admin_role_update_writes_audit_log(route_client, db_session) -> None:
    organization = await OrganizationRepository(db_session).create(
        name="Playbook Athletics",
        slug="playbook",
    )
    user_repo = UserRepository(db_session)
    super_admin = await user_repo.create(
        organization_id=organization.id,
        email="super@example.com",
        name="Super Admin",
        auth_provider="google",
        provider_subject="super-subject",
        role="super_admin",
    )
    target = await user_repo.create(
        organization_id=organization.id,
        email="athlete@example.com",
        name="Jordan Athlete",
        auth_provider="google",
        provider_subject="athlete-subject",
        role="athlete",
    )
    route_client.authenticate_as(super_admin)

    response = await route_client.client.patch(
        f"/api/v1/admin/users/{target.id}/role",
        json={"role": "admin"},
    )

    assert response.status_code == 200
    assert response.json()["role"] == "admin"
    assert target.role == "admin"

    audit_log = await db_session.scalar(
        select(AuditLog).where(AuditLog.action == "user.role_changed")
    )
    assert audit_log is not None
    assert audit_log.actor_user_id == super_admin.id
    assert audit_log.target_id == target.id
    assert audit_log.audit_metadata == {
        "previous_role": "athlete",
        "new_role": "admin",
    }


@pytest.mark.asyncio
async def test_admin_user_routes_require_super_admin(route_client, db_session) -> None:
    organization = await OrganizationRepository(db_session).create(
        name="Playbook Athletics",
        slug="playbook",
    )
    admin = await UserRepository(db_session).create(
        organization_id=organization.id,
        email="admin@example.com",
        name="Admin User",
        auth_provider="google",
        provider_subject="admin-subject",
        role="admin",
    )
    route_client.authenticate_as(admin)

    response = await route_client.client.get(
        "/api/v1/admin/users",
        headers={"X-Request-ID": "req-super"},
    )

    assert response.status_code == 403
    assert response.json()["error"] == {
        "code": "FORBIDDEN",
        "message": "Super admin role required",
        "retryable": False,
        "details": {"request_id": "req-super"},
    }
