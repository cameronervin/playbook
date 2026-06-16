from __future__ import annotations

from uuid import UUID
import re

import pytest

from app.agents.builders import chains_builder
from app.agents.executors.athlete_chat_executor import AthleteChatExecutor
from app.agents.states.athlete_chat_state import AthleteChatStructuredResponse
from app.infrastructure.streaming import InMemoryAgentStreamProvider
from app.repositories.conversations import (
    ConversationMessageRepository,
    ConversationRepository,
    ConversationFileRepository,
    MessageCitationRepository,
)
from app.repositories.identity import OrganizationRepository, UserRepository
from app.schemas.knowledgebase import KnowledgebaseResult, RetrievedChunk
from app.services.agent_stream_service import AgentStreamService


class FakeKnowledgebaseProvider:
    provider_name = "fake"

    def __init__(self) -> None:
        self.requests: list[dict[str, object]] = []
        self.admin_upload_requests: list[dict[str, object]] = []
        self.conversation_file_requests: list[dict[str, object]] = []
        self.conversation_file_chunks: list[RetrievedChunk] = []

    async def search(
        self,
        query: str,
        organization_id: UUID | str,
        max_docs: int = 10,
        score_threshold: float = 0.7,
        metadata_filter: dict | None = None,
        configuration_id: str | None = None,
    ) -> KnowledgebaseResult:
        self.requests.append(
            {
                "query": query,
                "organization_id": str(organization_id),
                "max_docs": max_docs,
                "score_threshold": score_threshold,
                "metadata_filter": metadata_filter,
                "configuration_id": configuration_id,
            }
        )
        return KnowledgebaseResult(
            query=query,
            context="context",
            sources=[
                RetrievedChunk(
                    text="NIL deals must be disclosed before participation.",
                    similarity_score=0.93,
                    metadata={
                        "document_id": "00000000-0000-0000-0000-000000000011",
                        "kb_service_document_id": "00000000-0000-0000-0000-000000000021",
                        "chunk_id": "00000000-0000-0000-0000-000000000012",
                        "chunk_index": 5,
                        "source_title": "NIL Handbook",
                        "source_date": "2026-01-15",
                        "is_official": True,
                        "priority": 10,
                    },
                )
            ],
            confidence=0.93,
            zero_hit=False,
            latency_ms=7,
        )

    async def search_admin_uploads(
        self,
        query: str,
        organization_id: UUID | str,
        max_docs: int = 10,
        score_threshold: float = 0.7,
        metadata_filter: dict | None = None,
        configuration_id: str | None = None,
    ) -> KnowledgebaseResult:
        result = await self.search(
            query=query,
            organization_id=organization_id,
            max_docs=max_docs,
            score_threshold=score_threshold,
            metadata_filter=metadata_filter,
            configuration_id=configuration_id,
        )
        self.admin_upload_requests.append(self.requests[-1])
        return result

    async def search_conversation_files(
        self,
        query: str,
        organization_id: UUID | str,
        conversation_id: UUID | str,
        file_ids: list[UUID | str] | None = None,
        max_docs: int = 10,
        score_threshold: float = 0.7,
        configuration_id: str | None = None,
    ) -> KnowledgebaseResult:
        request = {
            "query": query,
            "organization_id": str(organization_id),
            "conversation_id": str(conversation_id),
            "file_ids": [str(file_id) for file_id in file_ids or []],
            "max_docs": max_docs,
            "score_threshold": score_threshold,
            "configuration_id": configuration_id,
        }
        self.conversation_file_requests.append(request)
        requested_file_ids = set(request["file_ids"])
        chunks = [
            chunk
            for chunk in self.conversation_file_chunks
            if chunk.metadata.get("conversation_id") == str(conversation_id)
            and (
                not requested_file_ids
                or chunk.metadata.get("conversation_file_id") in requested_file_ids
            )
        ][:max_docs]
        return KnowledgebaseResult(
            query=query,
            context="context",
            sources=chunks,
            confidence=chunks[0].similarity_score if chunks else None,
            zero_hit=not chunks,
            latency_ms=6,
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


class FileContextChain:
    async def ainvoke(
        self,
        input: dict,
    ) -> dict[str, AthleteChatStructuredResponse]:
        message_render = "\n".join(
            str(getattr(message, "content", "")) for message in input["messages"]
        )
        assert "## Conversation File Context" not in message_render
        rendered = str(input.get("conversation_file_context", ""))
        match = re.search(r"\[(S-[^\]]+)\]", rendered)
        if match is None:
            return {
                "structured_response": AthleteChatStructuredResponse(
                    answer="I do not have file support.",
                    answer_type="unsupported",
                    cited_source_keys=[],
                    topic_labels=["nil"],
                    risk_labels=["compliance"],
                )
            }
        return {
            "structured_response": AthleteChatStructuredResponse(
                answer="The uploaded contract requires department approval.",
                answer_type="grounded_answer",
                cited_source_keys=[match.group(1)],
                topic_labels=["nil"],
                risk_labels=["compliance"],
            )
        }


class MixedSourceChain:
    def __init__(self, tool) -> None:
        self.tool = tool

    async def ainvoke(
        self,
        input: dict,
    ) -> dict[str, AthleteChatStructuredResponse]:
        tool_result = await self.tool.ainvoke({"query": "nil disclosure"})
        admin_source_key = tool_result.split("]", maxsplit=1)[0].lstrip("[")
        rendered_file_context = str(input.get("conversation_file_context", ""))
        file_match = re.search(r"\[(S-[^\]]+)\]", rendered_file_context)
        assert file_match is not None
        return {
            "structured_response": AthleteChatStructuredResponse(
                answer=(
                    "Disclose the NIL deal first, and get approval for the uploaded "
                    "contract clause."
                ),
                answer_type="grounded_answer",
                cited_source_keys=[admin_source_key, file_match.group(1)],
                topic_labels=["nil"],
                risk_labels=["compliance"],
            )
        }


def fake_chain_with_tool(*, tools: list, **_: object) -> ToolCallingChain:
    return ToolCallingChain(tools[0])


def fake_chain_without_tool(**_: object) -> NoToolChain:
    return NoToolChain()


def fake_chain_that_fails(**_: object) -> FailIfInvokedChain:
    return FailIfInvokedChain()


def fake_file_context_chain(**_: object) -> FileContextChain:
    return FileContextChain()


def fake_mixed_source_chain(*, tools: list, **_: object) -> MixedSourceChain:
    return MixedSourceChain(tools[0])


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

    kb_provider = FakeKnowledgebaseProvider()

    result = await AthleteChatExecutor(
        session=db_session,
        chat_model=object(),
        knowledgebase_provider=kb_provider,
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
    assert citations[0].source_metadata["kb_service_document_id"] == (
        "00000000-0000-0000-0000-000000000021"
    )
    assert citations[0].source_metadata["chunk_index"] == 5
    assert citations[0].source_metadata["priority"] == 10
    assert kb_provider.requests[0]["organization_id"] == str(organization.id)
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


@pytest.mark.asyncio
async def test_athlete_chat_executor_retrieves_attached_ready_file_and_persists_citation(
    db_session,
    test_settings,
    monkeypatch,
) -> None:
    monkeypatch.setattr(
        chains_builder,
        "create_athlete_chat_chain",
        fake_file_context_chain,
    )
    organization = await OrganizationRepository(db_session).create(
        name="Playbook Athletics",
        slug="playbook-agent-file",
    )
    athlete = await UserRepository(db_session).create(
        organization_id=organization.id,
        email="athlete-file@example.com",
        name="Jordan Athlete",
        auth_provider="google",
        provider_subject="athlete-file",
    )
    conversation = await ConversationRepository(db_session).create(
        organization_id=organization.id,
        athlete_id=athlete.id,
    )
    user_message = await ConversationMessageRepository(db_session).create(
        conversation_id=conversation.id,
        role="user",
        content="Does this uploaded NIL contract require approval?",
    )
    assistant_message = await ConversationMessageRepository(db_session).create(
        conversation_id=conversation.id,
        role="assistant",
        content="",
        status="streaming",
        metadata={"task_id": "task-file", "user_message_id": str(user_message.id)},
    )
    file_repo = ConversationFileRepository(db_session)
    file = await file_repo.create(
        conversation_id=conversation.id,
        uploaded_by=athlete.id,
        filename="nil-contract.pdf",
        content_type="application/pdf",
        size_bytes=123,
        storage_key="conversation-files/originals/nil-contract.pdf",
        extraction_status="ready",
    )
    await file_repo.update_ingestion_mirror(file, chunk_count=2)
    kb_provider = FakeKnowledgebaseProvider()
    kb_provider.conversation_file_chunks = [
        RetrievedChunk(
            text="The contract requires department approval before signing.",
            similarity_score=0.94,
            metadata={
                "source_type": "conversation_file",
                "organization_id": str(organization.id),
                "conversation_id": str(conversation.id),
                "conversation_file_id": str(file.id),
                "document_id": str(file.id),
                "kb_service_document_id": "00000000-0000-0000-0000-000000000071",
                "chunk_id": "00000000-0000-0000-0000-000000000072",
                "chunk_index": 4,
                "source_title": "nil-contract.pdf",
                "source_summary": "A summary of the uploaded contract.",
                "source_locator": {"type": "page", "page_number": 2},
            },
        )
    ]

    result = await AthleteChatExecutor(
        session=db_session,
        chat_model=object(),
        knowledgebase_provider=kb_provider,
        stream_service=AgentStreamService(InMemoryAgentStreamProvider()),
        settings=test_settings,
    ).execute(
        task_id="task-file",
        conversation_id=conversation.id,
        athlete_user_id=athlete.id,
        user_message_id=user_message.id,
        assistant_message_id=assistant_message.id,
        organization_id=organization.id,
        attached_file_ids=[file.id],
    )

    citations = await MessageCitationRepository(db_session).list_by_message(
        assistant_message.id
    )

    assert result["answer_type"] == "grounded_answer"
    assert kb_provider.conversation_file_requests[0]["file_ids"] == [str(file.id)]
    assert citations[0].document_id == file.id
    assert citations[0].chunk_id == UUID("00000000-0000-0000-0000-000000000072")
    assert citations[0].source_title == "nil-contract.pdf"
    assert citations[0].source_metadata["source_type"] == "conversation_file"
    assert citations[0].source_metadata["conversation_file_id"] == str(file.id)
    assert citations[0].source_metadata["source_locator"] == {
        "type": "page",
        "page_number": 2,
    }


@pytest.mark.asyncio
async def test_athlete_chat_executor_persists_mixed_admin_and_file_citations(
    db_session,
    test_settings,
    monkeypatch,
) -> None:
    monkeypatch.setattr(
        chains_builder,
        "create_athlete_chat_chain",
        fake_mixed_source_chain,
    )
    organization = await OrganizationRepository(db_session).create(
        name="Playbook Athletics",
        slug="playbook-agent-mixed",
    )
    athlete = await UserRepository(db_session).create(
        organization_id=organization.id,
        email="athlete-mixed@example.com",
        name="Jordan Athlete",
        auth_provider="google",
        provider_subject="athlete-mixed",
    )
    conversation = await ConversationRepository(db_session).create(
        organization_id=organization.id,
        athlete_id=athlete.id,
    )
    user_message = await ConversationMessageRepository(db_session).create(
        conversation_id=conversation.id,
        role="user",
        content="Can I sign this NIL deal if the uploaded contract mentions approval?",
    )
    assistant_message = await ConversationMessageRepository(db_session).create(
        conversation_id=conversation.id,
        role="assistant",
        content="",
        status="streaming",
        metadata={"task_id": "task-mixed", "user_message_id": str(user_message.id)},
    )
    file_repo = ConversationFileRepository(db_session)
    file = await file_repo.create(
        conversation_id=conversation.id,
        uploaded_by=athlete.id,
        filename="nil-contract.pdf",
        content_type="application/pdf",
        size_bytes=123,
        storage_key="conversation-files/originals/nil-contract.pdf",
        extraction_status="ready",
    )
    await file_repo.update_ingestion_mirror(file, chunk_count=1)
    kb_provider = FakeKnowledgebaseProvider()
    kb_provider.conversation_file_chunks = [
        RetrievedChunk(
            text="The uploaded contract requires department approval before signing.",
            similarity_score=0.95,
            metadata={
                "source_type": "conversation_file",
                "organization_id": str(organization.id),
                "conversation_id": str(conversation.id),
                "conversation_file_id": str(file.id),
                "document_id": str(file.id),
                "kb_service_document_id": "00000000-0000-0000-0000-000000000091",
                "chunk_id": "00000000-0000-0000-0000-000000000092",
                "chunk_index": 1,
                "source_title": "nil-contract.pdf",
            },
        )
    ]

    result = await AthleteChatExecutor(
        session=db_session,
        chat_model=object(),
        knowledgebase_provider=kb_provider,
        stream_service=AgentStreamService(InMemoryAgentStreamProvider()),
        settings=test_settings,
    ).execute(
        task_id="task-mixed",
        conversation_id=conversation.id,
        athlete_user_id=athlete.id,
        user_message_id=user_message.id,
        assistant_message_id=assistant_message.id,
        organization_id=organization.id,
        attached_file_ids=[file.id],
    )

    citations = await MessageCitationRepository(db_session).list_by_message(
        assistant_message.id
    )

    assert result["answer_type"] == "grounded_answer"
    assert len(citations) == 2
    assert citations[0].source_title == "NIL Handbook"
    assert citations[0].document_id == UUID("00000000-0000-0000-0000-000000000011")
    assert citations[0].source_metadata.get("source_type") != "conversation_file"
    assert citations[1].source_title == "nil-contract.pdf"
    assert citations[1].document_id == file.id
    assert citations[1].chunk_id == UUID("00000000-0000-0000-0000-000000000092")
    assert citations[1].source_metadata["source_type"] == "conversation_file"
    assert citations[1].source_metadata["conversation_file_id"] == str(file.id)


@pytest.mark.asyncio
async def test_athlete_chat_executor_searches_all_ready_files_when_none_attached(
    db_session,
    test_settings,
    monkeypatch,
) -> None:
    monkeypatch.setattr(
        chains_builder,
        "create_athlete_chat_chain",
        fake_file_context_chain,
    )
    organization = await OrganizationRepository(db_session).create(
        name="Playbook Athletics",
        slug="playbook-agent-file-all",
    )
    athlete = await UserRepository(db_session).create(
        organization_id=organization.id,
        email="athlete-file-all@example.com",
        name="Jordan Athlete",
        auth_provider="google",
        provider_subject="athlete-file-all",
    )
    conversation = await ConversationRepository(db_session).create(
        organization_id=organization.id,
        athlete_id=athlete.id,
    )
    user_message = await ConversationMessageRepository(db_session).create(
        conversation_id=conversation.id,
        role="user",
        content="What does my uploaded file say about approval?",
    )
    assistant_message = await ConversationMessageRepository(db_session).create(
        conversation_id=conversation.id,
        role="assistant",
        content="",
        status="streaming",
        metadata={"task_id": "task-file-all", "user_message_id": str(user_message.id)},
    )
    file_repo = ConversationFileRepository(db_session)
    ready_file = await file_repo.create(
        conversation_id=conversation.id,
        uploaded_by=athlete.id,
        filename="ready.pdf",
        content_type="application/pdf",
        size_bytes=123,
        storage_key="conversation-files/originals/ready.pdf",
        extraction_status="ready",
    )
    failed_file = await file_repo.create(
        conversation_id=conversation.id,
        uploaded_by=athlete.id,
        filename="failed.pdf",
        content_type="application/pdf",
        size_bytes=123,
        storage_key="conversation-files/originals/failed.pdf",
        extraction_status="failed",
    )
    zero_chunk_file = await file_repo.create(
        conversation_id=conversation.id,
        uploaded_by=athlete.id,
        filename="empty.pdf",
        content_type="application/pdf",
        size_bytes=123,
        storage_key="conversation-files/originals/empty.pdf",
        extraction_status="ready",
    )
    await file_repo.update_ingestion_mirror(ready_file, chunk_count=1)
    await file_repo.update_ingestion_mirror(failed_file, chunk_count=4)
    await file_repo.update_ingestion_mirror(zero_chunk_file, chunk_count=0)
    kb_provider = FakeKnowledgebaseProvider()
    kb_provider.conversation_file_chunks = [
        RetrievedChunk(
            text="The ready file says approval is required.",
            similarity_score=0.91,
            metadata={
                "source_type": "conversation_file",
                "organization_id": str(organization.id),
                "conversation_id": str(conversation.id),
                "conversation_file_id": str(ready_file.id),
                "document_id": str(ready_file.id),
                "chunk_id": "00000000-0000-0000-0000-000000000082",
                "source_title": "ready.pdf",
            },
        )
    ]

    await AthleteChatExecutor(
        session=db_session,
        chat_model=object(),
        knowledgebase_provider=kb_provider,
        stream_service=AgentStreamService(InMemoryAgentStreamProvider()),
        settings=test_settings,
    ).execute(
        task_id="task-file-all",
        conversation_id=conversation.id,
        athlete_user_id=athlete.id,
        user_message_id=user_message.id,
        assistant_message_id=assistant_message.id,
        organization_id=organization.id,
        attached_file_ids=[],
    )

    assert kb_provider.conversation_file_requests[0]["file_ids"] == [
        str(ready_file.id)
    ]
