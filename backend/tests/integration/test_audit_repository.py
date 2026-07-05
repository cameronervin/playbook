"""Integration tests for Playbook audit repositories."""

from datetime import UTC, datetime

import pytest

from app.repositories.audit import AuditLogRepository
from app.repositories.identity import OrganizationRepository, UserRepository


@pytest.mark.asyncio
async def test_audit_log_repository_creates_and_queries_append_only_events(db_session):
    org_repo = OrganizationRepository(db_session)
    user_repo = UserRepository(db_session)
    audit_repo = AuditLogRepository(db_session)
    organization = await org_repo.create(name="Playbook Athletics", slug="playbook")
    actor = await user_repo.create(
        organization_id=organization.id,
        email="admin@example.com",
        name="Admin User",
        auth_provider="google",
        provider_subject="admin-google-subject",
        role="super_admin",
    )

    audit_log = await audit_repo.create(
        organization_id=organization.id,
        actor_user_id=actor.id,
        action="user.role_changed",
        target_type="user",
        target_id=actor.id,
        metadata={"previous_role": "admin", "new_role": "super_admin"},
    )

    assert audit_log.id is not None
    assert audit_log.audit_metadata["new_role"] == "super_admin"

    results = await audit_repo.list_by_organization(
        organization.id,
        action="user.role_changed",
        target_type="user",
        target_id=actor.id,
        start_at=datetime(2000, 1, 1, tzinfo=UTC),
    )

    assert results == [audit_log]
    assert not hasattr(audit_repo, "update")
    assert not hasattr(audit_repo, "delete")


@pytest.mark.asyncio
async def test_audit_log_repository_filters_by_actor_and_date_range(db_session):
    org_repo = OrganizationRepository(db_session)
    user_repo = UserRepository(db_session)
    audit_repo = AuditLogRepository(db_session)
    organization = await org_repo.create(name="Playbook Athletics", slug="playbook")
    actor = await user_repo.create(
        organization_id=organization.id,
        email="admin@example.com",
        name="Admin User",
        auth_provider="google",
        provider_subject="admin-google-subject",
        role="admin",
    )

    matching = await audit_repo.create(
        organization_id=organization.id,
        actor_user_id=actor.id,
        action="kb.document_uploaded",
        target_type="kb_document",
        target_id=None,
        metadata={},
    )
    await audit_repo.create(
        organization_id=organization.id,
        actor_user_id=None,
        action="system.event",
        target_type="system",
        target_id=None,
        metadata={},
    )

    results = await audit_repo.list_by_organization(
        organization.id,
        actor_user_id=actor.id,
        end_at=datetime.now(UTC),
    )

    assert results == [matching]
