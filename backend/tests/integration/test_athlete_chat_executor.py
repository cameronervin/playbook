from __future__ import annotations

from uuid import UUID

import pytest

from app.agents.builders import chains_builder
from app.agents.executors.athlete_chat_executor import AthleteChatExecutor
from app.agents.states.athlete_chat_state import AthleteChatStructuredResponse
from app.infrastructure.streaming import InMemoryAgentStreamProvider
from app.repositories.conversations import (
    ConversationMessageRepository,
    ConversationRepository,
    MessageCitationRepository,
)
from app.repositories.identity import OrganizationRepository, UserRepository
from app.schemas.knowledgebase import KnowledgebaseResult, RetrievedChunk
from app.services.agent_stream_service import AgentStreamService


class FakeKnowledgebaseProvider:
    provider_name = "fake"

    async def search(
        self,
        query: str,
        max_docs: int = 10,
        score_threshold: float = 0.7,
        metadata_filter: dict | None = None,
        configuration_id: str | None = None,
    ) -> KnowledgebaseResult:
        return KnowledgebaseResult(
            query=query,
            context="context",
            sources=[
                RetrievedChunk(
                    text="NIL deals must be disclosed before participation.",
                    similarity_score=0.93,
                    metadata={
                        "document_id": "00000000-0000-0000-0000-000000000011",
                        "chunk_id": "00000000-0000-0000-0000-000000000012",
                        "source_title": "NIL Handbook",
                        "source_date": "2026-01-15",
                        "is_official": True,
                    },
                )
            ],
            confidence=0.93,
            zero_hit=False,
            latency_ms=7,
        )

    async def health_check(self) -> bool:
        return True

    async def resolve_configuration(self) -> str:
        return "fake-config"


class ToolCallingChain:
    def __init__(self, tool) -> None:
        self.tool = tool

    async def ainvoke(
        self,
        input: dict,
    ) -> dict[str, AthleteChatStructuredResponse]:
        tool_result = await self.tool.ainvoke({"query": "nil disclosure"})
        source_key = tool_result.split("]", maxsplit=1)[0].lstrip("[")
        return {
            "structured_response": AthleteChatStructuredResponse(
                answer="Yes, disclose it first.",
                answer_type="grounded_answer",
                cited_source_keys=[source_key],
                topic_labels=["nil"],
                risk_labels=["compliance"],
            )
        }


class NoToolChain:
    async def ainvoke(
        self,
        input: dict,
    ) -> dict[str, AthleteChatStructuredResponse]:
        return {
            "structured_response": AthleteChatStructuredResponse(
                answer="Yes, you can accept it.",
                answer_type="grounded_answer",
                cited_source_keys=[],
                topic_labels=["nil"],
                risk_labels=["compliance"],
            )
        }


class FailIfInvokedChain:
    async def ainvoke(
        self,
        input: dict,
    ) -> dict[str, AthleteChatStructuredResponse]:
        pytest.fail("safety bypass should not invoke the athlete chat agent")


def fake_chain_with_tool(*, tools: list, **_: object) -> ToolCallingChain:
    return ToolCallingChain(tools[0])


def fake_chain_without_tool(**_: object) -> NoToolChain:
    return NoToolChain()


def fake_chain_that_fails(**_: object) -> FailIfInvokedChain:
    return FailIfInvokedChain()


@pytest.mark.asyncio
async def test_athlete_chat_executor_persists_grounded_answer_and_citations(
    db_session,
    test_settings,
    monkeypatch,
) -> None:
    monkeypatch.setattr(
        chains_builder,
        "create_athlete_chat_chain",
        fake_chain_with_tool,
    )
    organization = await OrganizationRepository(db_session).create(
        name="Playbook Athletics",
        slug="playbook-agent",
    )
    athlete = await UserRepository(db_session).create(
        organization_id=organization.id,
        email="athlete-agent@example.com",
        name="Jordan Athlete",
        auth_provider="google",
        provider_subject="athlete-agent",
    )
    conversation = await ConversationRepository(db_session).create(
        organization_id=organization.id,
        athlete_id=athlete.id,
    )
    user_message = await ConversationMessageRepository(db_session).create(
        conversation_id=conversation.id,
        role="user",
        content="Can I accept this NIL deal?",
    )
    assistant_message = await ConversationMessageRepository(db_session).create(
        conversation_id=conversation.id,
        role="assistant",
        content="",
        status="streaming",
        metadata={"task_id": "task-grounded", "user_message_id": str(user_message.id)},
    )
    provider = InMemoryAgentStreamProvider()

    result = await AthleteChatExecutor(
        session=db_session,
        chat_model=object(),
        knowledgebase_provider=FakeKnowledgebaseProvider(),
        stream_service=AgentStreamService(provider),
        settings=test_settings,
    ).execute(
        task_id="task-grounded",
        conversation_id=conversation.id,
        athlete_user_id=athlete.id,
        user_message_id=user_message.id,
        assistant_message_id=assistant_message.id,
        organization_id=organization.id,
        attached_file_ids=[],
    )

    updated = await ConversationMessageRepository(db_session).get(assistant_message.id)
    citations = await MessageCitationRepository(db_session).list_by_message(
        assistant_message.id
    )
    records = [
        record async for record in provider.iter_events("task-grounded", after_id="0-0")
    ]

    assert result["status"] == "complete"
    assert updated is not None
    assert updated.status == "complete"
    assert updated.content.startswith("Yes, disclose it first.")
    assert updated.safety_outcome == "grounded_answer"
    assert updated.message_metadata["answer_type"] == "grounded_answer"
    assert citations[0].document_id == UUID("00000000-0000-0000-0000-000000000011")
    assert citations[0].chunk_id == UUID("00000000-0000-0000-0000-000000000012")
    assert citations[0].source_title == "NIL Handbook"
    assert records[-1].event.event_type == "complete"
    assert records[-1].event.data["citation_count"] == 1


@pytest.mark.asyncio
async def test_athlete_chat_executor_converts_required_no_source_answer_to_refusal(
    db_session,
    test_settings,
    monkeypatch,
) -> None:
    monkeypatch.setattr(
        chains_builder,
        "create_athlete_chat_chain",
        fake_chain_without_tool,
    )
    organization = await OrganizationRepository(db_session).create(
        name="Playbook Athletics",
        slug="playbook-agent-refusal",
    )
    athlete = await UserRepository(db_session).create(
        organization_id=organization.id,
        email="athlete-refusal@example.com",
        name="Jordan Athlete",
        auth_provider="google",
        provider_subject="athlete-refusal",
    )
    conversation = await ConversationRepository(db_session).create(
        organization_id=organization.id,
        athlete_id=athlete.id,
    )
    user_message = await ConversationMessageRepository(db_session).create(
        conversation_id=conversation.id,
        role="user",
        content="Can I accept this NIL deal?",
    )
    assistant_message = await ConversationMessageRepository(db_session).create(
        conversation_id=conversation.id,
        role="assistant",
        content="",
        status="streaming",
        metadata={"task_id": "task-refusal", "user_message_id": str(user_message.id)},
    )

    result = await AthleteChatExecutor(
        session=db_session,
        chat_model=object(),
        knowledgebase_provider=FakeKnowledgebaseProvider(),
        stream_service=AgentStreamService(InMemoryAgentStreamProvider()),
        settings=test_settings,
    ).execute(
        task_id="task-refusal",
        conversation_id=conversation.id,
        athlete_user_id=athlete.id,
        user_message_id=user_message.id,
        assistant_message_id=assistant_message.id,
        organization_id=organization.id,
        attached_file_ids=[],
    )

    updated = await ConversationMessageRepository(db_session).get(assistant_message.id)
    citations = await MessageCitationRepository(db_session).list_by_message(
        assistant_message.id
    )

    assert result["answer_type"] == "unsupported"
    assert updated is not None
    assert updated.status == "complete"
    assert "athletic department" in updated.content
    assert updated.safety_outcome == "unsupported"
    assert citations == []


@pytest.mark.asyncio
async def test_athlete_chat_executor_safety_bypass_skips_agent_and_persists_instruction(
    db_session,
    test_settings,
    monkeypatch,
) -> None:
    monkeypatch.setattr(
        chains_builder,
        "create_athlete_chat_chain",
        fake_chain_that_fails,
    )
    organization = await OrganizationRepository(db_session).create(
        name="Playbook Athletics",
        slug="playbook-agent-emergency",
    )
    athlete = await UserRepository(db_session).create(
        organization_id=organization.id,
        email="athlete-emergency@example.com",
        name="Jordan Athlete",
        auth_provider="google",
        provider_subject="athlete-emergency",
    )
    conversation = await ConversationRepository(db_session).create(
        organization_id=organization.id,
        athlete_id=athlete.id,
    )
    user_message = await ConversationMessageRepository(db_session).create(
        conversation_id=conversation.id,
        role="user",
        content="My teammate might hurt himself",
    )
    assistant_message = await ConversationMessageRepository(db_session).create(
        conversation_id=conversation.id,
        role="assistant",
        content="",
        status="streaming",
        metadata={"task_id": "task-emergency", "user_message_id": str(user_message.id)},
    )
    provider = InMemoryAgentStreamProvider()

    result = await AthleteChatExecutor(
        session=db_session,
        chat_model=object(),
        knowledgebase_provider=FakeKnowledgebaseProvider(),
        stream_service=AgentStreamService(provider),
        settings=test_settings,
    ).execute(
        task_id="task-emergency",
        conversation_id=conversation.id,
        athlete_user_id=athlete.id,
        user_message_id=user_message.id,
        assistant_message_id=assistant_message.id,
        organization_id=organization.id,
        attached_file_ids=[],
    )

    updated = await ConversationMessageRepository(db_session).get(assistant_message.id)
    citations = await MessageCitationRepository(db_session).list_by_message(
        assistant_message.id
    )
    records = [
        record async for record in provider.iter_events("task-emergency", after_id="0-0")
    ]

    assert result["answer_type"] == "emergency_instruction"
    assert updated is not None
    assert updated.status == "complete"
    assert "911" in updated.content
    assert updated.safety_outcome == "emergency_instruction"
    assert updated.message_metadata["kb_zero_hit"] is False
    assert citations == []
    assert records[-1].event.event_type == "complete"
