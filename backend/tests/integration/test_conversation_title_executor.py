from __future__ import annotations

import pytest

from app.agents.builders import chains_builder
from app.agents.executors.conversation_title_executor import ConversationTitleExecutor
from app.agents.states.conversation_title_state import ConversationTitleStructuredResponse
from app.repositories.conversations import (
    ConversationMessageRepository,
    ConversationRepository,
)
from app.repositories.identity import OrganizationRepository, UserRepository


class TitleChain:
    def __init__(self, title: str) -> None:
        self.title = title
        self.calls = 0

    async def ainvoke(
        self,
        input: dict,
        config: dict | None = None,
        context: object | None = None,
    ) -> dict[str, ConversationTitleStructuredResponse]:
        self.calls += 1
        return {
            "structured_response": ConversationTitleStructuredResponse(
                title=self.title,
            )
        }


@pytest.mark.asyncio
async def test_conversation_title_executor_persists_first_turn_title(
    db_session,
    test_settings,
    monkeypatch,
) -> None:
    title_chain = TitleChain("NIL Deal Disclosure")
    monkeypatch.setattr(
        chains_builder,
        "create_conversation_title_chain",
        lambda **_: title_chain,
    )
    organization = await OrganizationRepository(db_session).create(
        name="Playbook Athletics",
        slug="playbook-title",
    )
    athlete = await UserRepository(db_session).create(
        organization_id=organization.id,
        email="athlete-title@example.com",
        name="Jordan Athlete",
        auth_provider="google",
        provider_subject="athlete-title",
    )
    conversation = await ConversationRepository(db_session).create(
        organization_id=organization.id,
        athlete_id=athlete.id,
        title="Can I accept this NIL deal",
    )
    user_message = await ConversationMessageRepository(db_session).create(
        conversation_id=conversation.id,
        role="user",
        content="Can I accept this NIL deal?",
    )
    assistant_message = await ConversationMessageRepository(db_session).create(
        conversation_id=conversation.id,
        role="assistant",
        content="Disclose the NIL deal before signing.",
        status="complete",
        metadata={
            "task_id": "task-title",
            "user_message_id": str(user_message.id),
            "is_first_turn": True,
            "provisional_title": "Can I accept this NIL deal",
        },
    )

    title = await ConversationTitleExecutor(
        session=db_session,
        title_model=object(),
        settings=test_settings,
    ).execute(
        task_id="task-title",
        conversation_id=conversation.id,
        athlete_user_id=athlete.id,
        user_message_id=user_message.id,
        assistant_message_id=assistant_message.id,
        organization_id=organization.id,
    )

    updated = await ConversationRepository(db_session).get_for_athlete(
        conversation_id=conversation.id,
        organization_id=organization.id,
        athlete_id=athlete.id,
    )
    assert title == "NIL Deal Disclosure"
    assert updated is not None
    assert updated.title == "NIL Deal Disclosure"
    assert title_chain.calls == 1


@pytest.mark.asyncio
async def test_conversation_title_executor_skips_follow_up_turn_without_model_call(
    db_session,
    test_settings,
    monkeypatch,
) -> None:
    title_chain = TitleChain("Should Not Run")
    monkeypatch.setattr(
        chains_builder,
        "create_conversation_title_chain",
        lambda **_: title_chain,
    )
    organization = await OrganizationRepository(db_session).create(
        name="Playbook Athletics",
        slug="playbook-title-skip",
    )
    athlete = await UserRepository(db_session).create(
        organization_id=organization.id,
        email="athlete-title-skip@example.com",
        name="Jordan Athlete",
        auth_provider="google",
        provider_subject="athlete-title-skip",
    )
    conversation = await ConversationRepository(db_session).create(
        organization_id=organization.id,
        athlete_id=athlete.id,
        title="Existing Title",
    )
    user_message = await ConversationMessageRepository(db_session).create(
        conversation_id=conversation.id,
        role="user",
        content="What about tomorrow?",
    )
    assistant_message = await ConversationMessageRepository(db_session).create(
        conversation_id=conversation.id,
        role="assistant",
        content="Follow the current travel policy.",
        status="complete",
        metadata={
            "task_id": "task-title-skip",
            "user_message_id": str(user_message.id),
        },
    )

    title = await ConversationTitleExecutor(
        session=db_session,
        title_model=object(),
        settings=test_settings,
    ).execute(
        task_id="task-title-skip",
        conversation_id=conversation.id,
        athlete_user_id=athlete.id,
        user_message_id=user_message.id,
        assistant_message_id=assistant_message.id,
        organization_id=organization.id,
    )

    assert title is None
    assert conversation.title == "Existing Title"
    assert title_chain.calls == 0


@pytest.mark.asyncio
async def test_conversation_title_executor_skips_when_title_was_already_changed(
    db_session,
    test_settings,
    monkeypatch,
) -> None:
    title_chain = TitleChain("Should Not Overwrite")
    monkeypatch.setattr(
        chains_builder,
        "create_conversation_title_chain",
        lambda **_: title_chain,
    )
    organization = await OrganizationRepository(db_session).create(
        name="Playbook Athletics",
        slug="playbook-title-changed",
    )
    athlete = await UserRepository(db_session).create(
        organization_id=organization.id,
        email="athlete-title-changed@example.com",
        name="Jordan Athlete",
        auth_provider="google",
        provider_subject="athlete-title-changed",
    )
    conversation = await ConversationRepository(db_session).create(
        organization_id=organization.id,
        athlete_id=athlete.id,
        title="Manual Title",
    )
    user_message = await ConversationMessageRepository(db_session).create(
        conversation_id=conversation.id,
        role="user",
        content="Can I accept this NIL deal?",
    )
    assistant_message = await ConversationMessageRepository(db_session).create(
        conversation_id=conversation.id,
        role="assistant",
        content="Disclose the NIL deal before signing.",
        status="complete",
        metadata={
            "task_id": "task-title-changed",
            "user_message_id": str(user_message.id),
            "is_first_turn": True,
            "provisional_title": "Can I accept this NIL deal",
        },
    )

    title = await ConversationTitleExecutor(
        session=db_session,
        title_model=object(),
        settings=test_settings,
    ).execute(
        task_id="task-title-changed",
        conversation_id=conversation.id,
        athlete_user_id=athlete.id,
        user_message_id=user_message.id,
        assistant_message_id=assistant_message.id,
        organization_id=organization.id,
    )

    assert title is None
    assert conversation.title == "Manual Title"
    assert title_chain.calls == 0
