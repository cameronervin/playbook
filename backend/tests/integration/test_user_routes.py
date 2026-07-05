"""Route-level tests for current-user profile endpoints."""

from __future__ import annotations

import pytest

from app.repositories.identity import OrganizationRepository, UserRepository


@pytest.mark.asyncio
async def test_current_user_route_returns_public_profile(route_client, db_session) -> None:
    organization = await OrganizationRepository(db_session).create(
        name="Playbook Athletics",
        slug="playbook",
    )
    athlete = await UserRepository(db_session).create(
        organization_id=organization.id,
        email="athlete@example.com",
        name="Jordan Athlete",
        auth_provider="google",
        provider_subject="google-subject",
        sport_team="Basketball",
    )
    route_client.authenticate_as(athlete)

    response = await route_client.client.get("/api/v1/users/me")

    assert response.status_code == 200
    assert response.json()["email"] == "athlete@example.com"
    assert response.json()["profile_complete"] is True


@pytest.mark.asyncio
async def test_update_profile_completes_athlete_profile(route_client, db_session) -> None:
    organization = await OrganizationRepository(db_session).create(
        name="Playbook Athletics",
        slug="playbook",
    )
    athlete = await UserRepository(db_session).create(
        organization_id=organization.id,
        email="athlete@example.com",
        name="Unfinished Athlete",
        auth_provider="google",
        provider_subject="google-subject",
        sport_team=None,
    )
    route_client.authenticate_as(athlete)

    response = await route_client.client.patch(
        "/api/v1/users/me/profile",
        json={"name": " Jordan Athlete ", "sport_team": " Basketball "},
    )

    assert response.status_code == 200
    assert response.json()["name"] == "Jordan Athlete"
    assert response.json()["sport_team"] == "Basketball"
    assert response.json()["profile_complete"] is True
    assert response.json()["next_route"] == "/chat"
    assert athlete.name == "Jordan Athlete"
    assert athlete.sport_team == "Basketball"


@pytest.mark.asyncio
async def test_update_profile_validates_required_fields(route_client, db_session) -> None:
    organization = await OrganizationRepository(db_session).create(
        name="Playbook Athletics",
        slug="playbook",
    )
    athlete = await UserRepository(db_session).create(
        organization_id=organization.id,
        email="athlete@example.com",
        name="Jordan Athlete",
        auth_provider="google",
        provider_subject="google-subject",
    )
    route_client.authenticate_as(athlete)

    response = await route_client.client.patch(
        "/api/v1/users/me/profile",
        json={"name": "", "sport_team": ""},
        headers={"X-Request-ID": "req-profile"},
    )

    assert response.status_code == 422
    error = response.json()["error"]
    assert error["code"] == "VALIDATION_ERROR"
    assert error["details"]["request_id"] == "req-profile"


@pytest.mark.asyncio
async def test_update_profile_requires_athlete_role(route_client, db_session) -> None:
    organization = await OrganizationRepository(db_session).create(
        name="Playbook Athletics",
        slug="playbook",
    )
    admin = await UserRepository(db_session).create(
        organization_id=organization.id,
        email="admin@example.com",
        name="Admin User",
        auth_provider="google",
        provider_subject="google-subject",
        role="admin",
    )
    route_client.authenticate_as(admin)

    response = await route_client.client.patch(
        "/api/v1/users/me/profile",
        json={"name": "Admin User", "sport_team": "Operations"},
        headers={"X-Request-ID": "req-forbidden"},
    )

    assert response.status_code == 403
    assert response.json()["error"] == {
        "code": "FORBIDDEN",
        "message": "Athlete role required",
        "retryable": False,
        "details": {"request_id": "req-forbidden"},
    }
