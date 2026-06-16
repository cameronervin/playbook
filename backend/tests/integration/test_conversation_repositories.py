"""Integration tests for Playbook conversation repositories."""

from datetime import UTC, datetime

import pytest

from app.repositories.conversations import (
    ConversationFileRepository,
    ConversationMessageRepository,
    ConversationRepository,
    MessageCitationRepository,
)
from app.repositories.identity import OrganizationRepository, UserRepository


@pytest.mark.asyncio
async def test_conversation_repository_creates_lists_and_scopes_to_athlete(
    db_session,
):
    org_repo = OrganizationRepository(db_session)
    user_repo = UserRepository(db_session)
    conversation_repo = ConversationRepository(db_session)
    organization = await org_repo.create(name="Playbook Athletics", slug="playbook")
    athlete = await user_repo.create(
        organization_id=organization.id,
        email="athlete@example.com",
        name="Jordan Athlete",
        auth_provider="google",
        provider_subject="athlete-google-subject",
    )
    other_athlete = await user_repo.create(
        organization_id=organization.id,
        email="other@example.com",
        name="Other Athlete",
        auth_provider="google",
        provider_subject="other-google-subject",
    )

    conversation = await conversation_repo.create(
        organization_id=organization.id,
        athlete_id=athlete.id,
        title="NIL question",
    )

    assert conversation.id is not None
    assert conversation.status == "active"

    by_owner = await conversation_repo.get_for_athlete(
        conversation_id=conversation.id,
        organization_id=organization.id,
        athlete_id=athlete.id,
    )
    by_other_athlete = await conversation_repo.get_for_athlete(
        conversation_id=conversation.id,
        organization_id=organization.id,
        athlete_id=other_athlete.id,
    )
    conversations = await conversation_repo.list_for_athlete(
        organization_id=organization.id,
        athlete_id=athlete.id,
    )

    assert by_owner is conversation
    assert by_other_athlete is None
    assert conversations == [conversation]


@pytest.mark.asyncio
async def test_message_repository_appends_orders_and_updates_messages(db_session):
    org_repo = OrganizationRepository(db_session)
    user_repo = UserRepository(db_session)
    conversation_repo = ConversationRepository(db_session)
    message_repo = ConversationMessageRepository(db_session)
    organization = await org_repo.create(name="Playbook Athletics", slug="playbook")
    athlete = await user_repo.create(
        organization_id=organization.id,
        email="athlete@example.com",
        name="Jordan Athlete",
        auth_provider="google",
        provider_subject="athlete-google-subject",
    )
    conversation = await conversation_repo.create(
        organization_id=organization.id,
        athlete_id=athlete.id,
    )

    user_message = await message_repo.create(
        conversation_id=conversation.id,
        role="user",
        content="Can I accept this NIL deal?",
        topic_labels=["nil"],
        risk_labels=["compliance"],
        created_at=datetime(2026, 1, 1, tzinfo=UTC),
    )
    assistant_message = await message_repo.create(
        conversation_id=conversation.id,
        role="assistant",
        content="",
        status="streaming",
        created_at=datetime(2026, 1, 2, tzinfo=UTC),
    )
    await message_repo.update_status_and_content(
        assistant_message,
        status="complete",
        content="Short answer with a citation.",
        safety_outcome="grounded_answer",
        topic_labels=["nil"],
        risk_labels=["compliance"],
        metadata={"model": "playbook-chat"},
    )

    messages = await message_repo.list_by_conversation(conversation.id)
    bounded_messages = await message_repo.list_recent_for_conversation(
        conversation.id,
        limit=1,
    )

    assert messages == [user_message, assistant_message]
    assert bounded_messages == [assistant_message]
    assert assistant_message.status == "complete"
    assert assistant_message.content == "Short answer with a citation."
    assert assistant_message.message_metadata == {"model": "playbook-chat"}


@pytest.mark.asyncio
async def test_message_citation_repository_appends_and_orders_by_rank(db_session):
    org_repo = OrganizationRepository(db_session)
    user_repo = UserRepository(db_session)
    conversation_repo = ConversationRepository(db_session)
    message_repo = ConversationMessageRepository(db_session)
    citation_repo = MessageCitationRepository(db_session)
    organization = await org_repo.create(name="Playbook Athletics", slug="playbook")
    athlete = await user_repo.create(
        organization_id=organization.id,
        email="athlete@example.com",
        name="Jordan Athlete",
        auth_provider="google",
        provider_subject="athlete-google-subject",
    )
    conversation = await conversation_repo.create(
        organization_id=organization.id,
        athlete_id=athlete.id,
    )
    assistant_message = await message_repo.create(
        conversation_id=conversation.id,
        role="assistant",
        content="Short answer.",
    )

    second = await citation_repo.create(
        message_id=assistant_message.id,
        source_title="Compliance FAQ",
        rank=2,
        source_metadata={"source_date": "2026-01-01"},
    )
    first = await citation_repo.create(
        message_id=assistant_message.id,
        source_title="NIL Handbook",
        rank=1,
        source_metadata={"source_date": "2026-02-01"},
    )

    citations = await citation_repo.list_by_message(assistant_message.id)

    assert citations == [first, second]


@pytest.mark.asyncio
async def test_message_citation_repository_lists_by_messages(db_session):
    org_repo = OrganizationRepository(db_session)
    user_repo = UserRepository(db_session)
    conversation_repo = ConversationRepository(db_session)
    message_repo = ConversationMessageRepository(db_session)
    citation_repo = MessageCitationRepository(db_session)
    organization = await org_repo.create(name="Playbook Athletics", slug="playbook")
    athlete = await user_repo.create(
        organization_id=organization.id,
        email="athlete@example.com",
        name="Jordan Athlete",
        auth_provider="google",
        provider_subject="athlete-google-subject",
    )
    conversation = await conversation_repo.create(
        organization_id=organization.id,
        athlete_id=athlete.id,
    )
    first_message = await message_repo.create(
        conversation_id=conversation.id,
        role="assistant",
        content="First answer.",
    )
    second_message = await message_repo.create(
        conversation_id=conversation.id,
        role="assistant",
        content="Second answer.",
    )

    second_citation = await citation_repo.create(
        message_id=second_message.id,
        source_title="Second source",
        rank=1,
    )
    first_second_rank = await citation_repo.create(
        message_id=first_message.id,
        source_title="First source rank two",
        rank=2,
    )
    first_first_rank = await citation_repo.create(
        message_id=first_message.id,
        source_title="First source rank one",
        rank=1,
    )

    citations_by_message = await citation_repo.list_by_messages(
        [first_message.id, second_message.id],
    )

    assert citations_by_message[first_message.id] == [
        first_first_rank,
        first_second_rank,
    ]
    assert citations_by_message[second_message.id] == [second_citation]


@pytest.mark.asyncio
async def test_conversation_file_repositories_create_list_with_zero_chunk_count(
    db_session,
):
    org_repo = OrganizationRepository(db_session)
    user_repo = UserRepository(db_session)
    conversation_repo = ConversationRepository(db_session)
    message_repo = ConversationMessageRepository(db_session)
    file_repo = ConversationFileRepository(db_session)
    organization = await org_repo.create(name="Playbook Athletics", slug="playbook")
    athlete = await user_repo.create(
        organization_id=organization.id,
        email="athlete@example.com",
        name="Jordan Athlete",
        auth_provider="google",
        provider_subject="athlete-google-subject",
    )
    conversation = await conversation_repo.create(
        organization_id=organization.id,
        athlete_id=athlete.id,
    )
    message = await message_repo.create(
        conversation_id=conversation.id,
        role="user",
        content="Can you review this contract?",
    )
    file = await file_repo.create(
        conversation_id=conversation.id,
        uploaded_by=athlete.id,
        filename="contract.pdf",
        content_type="application/pdf",
        size_bytes=123456,
        storage_key="conversations/org/conversation/file/contract.pdf",
        message_id=message.id,
    )
    await file_repo.update_extraction_status(
        file,
        extraction_status="ready",
        extracted_text_ref="conversations/extracted/contract.json",
        extracted_text_sha256="a" * 64,
        extracted_char_count=24,
        extraction_metadata={"extractor": "test"},
    )

    files_with_counts = await file_repo.list_by_conversation_with_chunk_counts(
        conversation.id,
    )

    assert files_with_counts == [(file, 0)]
    assert file.extraction_status == "ready"
    assert file.extraction_metadata == {"extractor": "test"}
