from __future__ import annotations

import asyncio
from types import SimpleNamespace
from typing import Any
from uuid import UUID, uuid4

import pytest

from app.agents.tools.knowledgebase import register_knowledgebase_sources
from app.repositories.conversations import (
    ConversationMessageRepository,
    MessageCitationRepository,
)
from app.schemas.knowledgebase import RetrievedChunk
from evals.specs import playbook_adapters
from evals.specs.playbook_adapters import (
    RecordingKnowledgebaseProvider,
    RecordingStreamService,
    build_graph_run,
    graph_run_events,
    make_admin_chat_executor_adapter,
    make_athlete_chat_executor_adapter,
    make_conversation_title_executor_adapter,
)

ORG_ID = UUID("00000000-0000-0000-0000-000000000099")
CONVERSATION_ID = UUID("00000000-0000-0000-0000-000000000098")
FILE_ID = UUID("00000000-0000-0000-0000-000000000097")


def _admin_chunk() -> RetrievedChunk:
    return RetrievedChunk(
        text="NIL deals must be disclosed before signing.",
        metadata={
            "source_type": "admin_upload",
            "playbook_document_id": "00000000-0000-0000-0000-000000000011",
            "chunk_id": "00000000-0000-0000-0000-000000000012",
            "source_title": "NIL Handbook",
        },
        similarity_score=0.91,
    )


def _file_chunk() -> RetrievedChunk:
    return RetrievedChunk(
        text="The uploaded contract contains a thirty-day review window.",
        metadata={
            "source_type": "conversation_file",
            "conversation_id": str(CONVERSATION_ID),
            "conversation_file_id": str(FILE_ID),
            "chunk_id": "00000000-0000-0000-0000-000000000013",
            "source_title": "Uploaded NIL Contract",
        },
        similarity_score=0.86,
    )


def _source_key_from_event(run: object) -> str:
    source_key = run.events[0]["retriever"]["sources"][0].get("source_key")
    assert isinstance(source_key, str)
    return source_key


@pytest.mark.asyncio
async def test_recording_knowledgebase_provider_records_shared_and_file_searches() -> None:
    provider = RecordingKnowledgebaseProvider(
        admin_upload_chunks=[_admin_chunk()],
        conversation_file_chunks=[_file_chunk()],
    )

    admin_result = await provider.search_admin_uploads(
        query="nil disclosure",
        organization_id=ORG_ID,
        max_docs=5,
        score_threshold=0.5,
        metadata_filter={"visibility_policy": {"scope": "all_athletes"}},
    )
    file_result = await provider.search_conversation_files(
        query="contract review window",
        organization_id=ORG_ID,
        conversation_id=CONVERSATION_ID,
        file_ids=[FILE_ID],
        max_docs=3,
        score_threshold=0.4,
    )

    assert admin_result.context == "NIL deals must be disclosed before signing."
    assert file_result.context == "The uploaded contract contains a thirty-day review window."
    assert [record.tool_name for record in provider.records] == [
        "search_admin_uploads",
        "search_conversation_files",
    ]
    assert provider.records[1].request["file_ids"] == [str(FILE_ID)]


@pytest.mark.asyncio
async def test_build_graph_run_emits_retrieval_citation_and_reference_events() -> None:
    provider = RecordingKnowledgebaseProvider(admin_upload_chunks=[_admin_chunk()])
    await provider.search_admin_uploads(query="nil disclosure", organization_id=ORG_ID)
    stream_service = RecordingStreamService()
    await stream_service.publish_chunk("task-eval", content="Grounded ")
    await stream_service.publish_chunk("task-eval", content="answer.")
    citation = {"source_key": "S-1", "source_title": "NIL Handbook"}
    reference = {"type": "metric", "id": "analytics.summary"}

    run = build_graph_run(
        input_data={"question": "Can I sign this NIL deal?"},
        executor_output={
            "status": "complete",
            "answer_type": "grounded_answer",
            "citations": [citation],
            "references": [reference],
        },
        kb_provider=provider,
        stream_service=stream_service,
    )

    assert run.output["answer"] == "Grounded answer."
    assert run.output["citations"] == [citation]
    assert {"citations": {"sources": [citation]}} in run.events
    assert {"admin_references": {"references": [reference]}} in run.events
    assert run.events[0]["retriever"]["documents"] == [
        "NIL deals must be disclosed before signing."
    ]
    assert _source_key_from_event(run).startswith("S-")


def test_graph_run_events_accept_explicit_citations_and_admin_references() -> None:
    citation = {"source_key": "S-1", "source_title": "NIL Handbook"}
    reference = {"type": "dashboard_insight", "id": "insight-1"}

    events = graph_run_events(citations=[citation], admin_references=[reference])

    assert events == [
        {"citations": {"sources": [citation]}},
        {"admin_references": {"references": [reference]}},
    ]


@pytest.mark.asyncio
async def test_athlete_chat_executor_adapter_runs_production_executor_with_fakes(
    test_settings,
) -> None:
    graph = AthleteGraphDouble()
    provider = RecordingKnowledgebaseProvider(admin_upload_chunks=[_admin_chunk()])
    adapter = make_athlete_chat_executor_adapter(
        session=object(),
        settings=test_settings,
        chat_model=object(),
        knowledgebase_provider=provider,
        graph_provider=SimpleNamespace(athlete_chat_graph=lambda: graph),
        title_executor_factory=NoopTitleExecutor,
    )
    item_input = {
        "task_id": "task-athlete-eval",
        "conversation_id": str(uuid4()),
        "athlete_user_id": str(uuid4()),
        "user_message_id": str(uuid4()),
        "assistant_message_id": str(uuid4()),
        "organization_id": str(ORG_ID),
        "attached_file_ids": [],
    }

    run = await adapter(item={"input": item_input})

    assert graph.initial_state["task_id"] == "task-athlete-eval"
    assert run.output["answer"] == "Disclose the deal before signing."
    assert run.output["answer_type"] == "grounded_answer"
    assert run.events[0]["retriever"]["tool_name"] == "search_admin_uploads"
    assert run.events[0]["retriever"]["documents"] == [
        "NIL deals must be disclosed before signing."
    ]


@pytest.mark.asyncio
async def test_athlete_chat_executor_adapter_auto_seeds_and_uses_fixture_kb(
    test_settings,
    db_session,
) -> None:
    graph = AthleteGraphDouble()
    adapter = make_athlete_chat_executor_adapter(
        session=db_session,
        settings=test_settings,
        chat_model=object(),
        graph_provider=SimpleNamespace(athlete_chat_graph=lambda: graph),
        title_executor_factory=NoopTitleExecutor,
    )

    run = await adapter(
        item={
            "input": {
                "question": "do i have to file before i post a same-day NIL thing?",
                "retrieved_source_ids": ["src:nil-disclosure-2026#chunk-1"],
            }
        }
    )

    assert graph.initial_state["conversation_id"] == run.input["conversation_id"]
    assert graph.initial_state["user_message_id"] == run.input["user_message_id"]
    assert run.events[0]["retriever"]["sources"][0]["metadata"]["source_id"] == (
        "src:nil-disclosure-2026#chunk-1"
    )
    assert _source_key_from_event(run).startswith("S-")
    assert "Same-day opportunities" in run.events[0]["retriever"]["documents"][0]


@pytest.mark.asyncio
async def test_athlete_chat_executor_adapter_enriches_persisted_citation_evidence(
    test_settings,
    db_session,
) -> None:
    adapter = make_athlete_chat_executor_adapter(
        session=db_session,
        settings=test_settings,
        chat_model=object(),
        executor_cls=PersistingAthleteExecutor,
    )

    run = await adapter(
        item={
            "input": {
                "question": "do i have to disclose before posting?",
                "retrieved_source_ids": ["src:nil-disclosure-2026#chunk-1"],
            }
        }
    )

    event_source_key = _source_key_from_event(run)
    assert run.output["answer"] == "Disclose before posting."
    assert run.output["cited_source_keys"] == [event_source_key]
    citation_event = next(event["citations"] for event in run.events if "citations" in event)
    assert citation_event["sources"][0]["source_key"] == event_source_key


@pytest.mark.asyncio
async def test_admin_chat_executor_adapter_emits_admin_reference_events(
    test_settings,
) -> None:
    graph = AdminGraphDouble()
    adapter = make_admin_chat_executor_adapter(
        session=object(),
        settings=test_settings,
        chat_model=object(),
        graph_provider=SimpleNamespace(admin_chat_graph=lambda: graph),
    )
    item_input = {
        "task_id": "task-admin-eval",
        "session_id": str(uuid4()),
        "admin_user_id": str(uuid4()),
        "user_message_id": str(uuid4()),
        "assistant_message_id": str(uuid4()),
        "organization_id": str(ORG_ID),
        "window_start": "2026-06-01T00:00:00+00:00",
        "window_end": "2026-07-01T00:00:00+00:00",
    }

    run = await adapter(item={"input": item_input})

    assert graph.initial_state["session_id"] == item_input["session_id"]
    assert run.output["answer"] == "There were 12 NIL questions."
    assert run.output["references"] == [{"type": "metric", "id": "analytics.summary"}]
    assert {"admin_references": {"references": run.output["references"]}} in run.events


@pytest.mark.asyncio
async def test_admin_chat_executor_adapter_auto_seeds_snapshot_references(
    test_settings,
    db_session,
) -> None:
    graph = AdminGraphDouble()
    adapter = make_admin_chat_executor_adapter(
        session=db_session,
        settings=test_settings,
        chat_model=object(),
        graph_provider=SimpleNamespace(admin_chat_graph=lambda: graph),
    )

    run = await adapter(
        item={
            "input": {
                "question": "what moved this week?",
                "window": "last_7_days",
                "snapshot": {
                    "query_volume": 3,
                    "top_topics": [{"label": "nil", "count": 2}],
                    "unanswered_count": 1,
                    "risk_counts": {"compliance": 2},
                },
            }
        }
    )

    query_refs = [
        ref for ref in run.input["allowed_references"] if ref["type"] == "query"
    ]
    assert graph.initial_state["session_id"] == run.input["session_id"]
    assert len(query_refs) == 3
    assert {"type": "metric", "id": "analytics.summary"} in run.input["allowed_references"]


@pytest.mark.asyncio
async def test_default_eval_session_factory_isolates_concurrent_engines(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    FakeEngine.counter = 0
    created_engines: list[FakeEngine] = []

    def fake_create_async_engine(database_url: str, **kwargs: Any) -> "FakeEngine":
        engine = FakeEngine(database_url=database_url, kwargs=kwargs)
        created_engines.append(engine)
        return engine

    def fake_async_sessionmaker(
        engine: "FakeEngine",
        *,
        class_: object,
        expire_on_commit: bool,
    ) -> Any:
        assert class_ is playbook_adapters.AsyncSession
        assert expire_on_commit is False
        return lambda: FakeSession(engine)

    monkeypatch.setattr(
        playbook_adapters,
        "create_async_engine",
        fake_create_async_engine,
    )
    monkeypatch.setattr(
        playbook_adapters,
        "async_sessionmaker",
        fake_async_sessionmaker,
    )

    factory = playbook_adapters._default_session_factory(
        SimpleNamespace(DATABASE_URL="postgresql+asyncpg://eval-db")
    )

    async def open_session() -> str:
        async with factory() as session:
            return session.label

    labels = await asyncio.gather(open_session(), open_session())

    assert labels == ["session-1", "session-2"]
    assert [engine.database_url for engine in created_engines] == [
        "postgresql+asyncpg://eval-db",
        "postgresql+asyncpg://eval-db",
    ]
    assert all(
        engine.kwargs["poolclass"] is playbook_adapters.NullPool
        for engine in created_engines
    )
    assert all(engine.disposed for engine in created_engines)


@pytest.mark.asyncio
async def test_conversation_title_adapter_allows_fixture_seeding(
    test_settings,
) -> None:
    seeded_ids = {
        "task_id": "task-title-eval",
        "conversation_id": str(uuid4()),
        "athlete_user_id": str(uuid4()),
        "user_message_id": str(uuid4()),
        "assistant_message_id": str(uuid4()),
        "organization_id": str(ORG_ID),
    }

    async def seed_item(*, item_input: dict[str, Any], session: object) -> dict[str, str]:
        assert item_input == {"scenario": "first-turn-title"}
        assert session is fake_session
        return seeded_ids

    fake_session = object()
    FakeConversationTitleExecutor.execute_calls.clear()
    adapter = make_conversation_title_executor_adapter(
        session=fake_session,
        settings=test_settings,
        title_model=object(),
        executor_cls=FakeConversationTitleExecutor,
        item_seeder=seed_item,
    )

    run = await adapter(item={"input": {"scenario": "first-turn-title"}})

    assert run.output == {"conversation_title": "NIL Deal Disclosure"}
    assert FakeConversationTitleExecutor.execute_calls == [seeded_ids]


class AthleteGraphDouble:
    def __init__(self) -> None:
        self.initial_state: dict[str, Any] = {}

    async def astream(
        self,
        initial_state: dict[str, Any],
        config: dict[str, Any] | None = None,
        context: Any | None = None,
        stream_mode: list[str] | None = None,
        version: str | None = None,
    ):
        self.initial_state = initial_state
        await context.knowledgebase_provider.search_admin_uploads(
            query="nil disclosure",
            organization_id=initial_state["organization_id"],
        )
        await context.stream_service.publish_chunk(
            initial_state["task_id"],
            content="Disclose the deal before signing.",
        )
        yield (
            "updates",
            {
                "save_state": {
                    "completion_result": {
                        "status": "complete",
                        "task_id": initial_state["task_id"],
                        "assistant_message_id": initial_state["assistant_message_id"],
                        "answer_type": "grounded_answer",
                        "citation_count": 1,
                        "answer": "Disclose the deal before signing.",
                    }
                }
            },
        )


class PersistingAthleteExecutor:
    def __init__(self, **kwargs: Any) -> None:
        self.session = kwargs["session"]
        self.knowledgebase_provider = kwargs["knowledgebase_provider"]

    async def execute(self, **kwargs: Any) -> dict[str, Any]:
        result = await self.knowledgebase_provider.search_admin_uploads(
            query="nil disclosure",
            organization_id=kwargs["organization_id"],
        )
        registry: dict[str, Any] = {}
        sources = register_knowledgebase_sources(result, registry=registry)
        source_key = sources[0].source_key
        assistant_message = await ConversationMessageRepository(self.session).get(
            kwargs["assistant_message_id"]
        )
        assert assistant_message is not None
        await ConversationMessageRepository(self.session).update_status_and_content(
            assistant_message,
            status="complete",
            content="Disclose before posting.",
            safety_outcome="grounded_answer",
            metadata={
                **assistant_message.message_metadata,
                "answer_type": "grounded_answer",
                "source_keys": [source_key],
            },
        )
        await MessageCitationRepository(self.session).delete_by_message(
            kwargs["assistant_message_id"]
        )
        await MessageCitationRepository(self.session).create(
            message_id=kwargs["assistant_message_id"],
            source_title=sources[0].source_title,
            source_metadata=sources[0].metadata,
            rank=1,
        )
        await self.session.commit()
        return {
            "status": "complete",
            "task_id": kwargs["task_id"],
            "assistant_message_id": str(kwargs["assistant_message_id"]),
            "answer_type": "grounded_answer",
            "citation_count": 1,
            "answer": "Disclose before posting.",
        }


class AdminGraphDouble:
    def __init__(self) -> None:
        self.initial_state: dict[str, Any] = {}

    async def astream(
        self,
        initial_state: dict[str, Any],
        config: dict[str, Any] | None = None,
        context: Any | None = None,
        stream_mode: list[str] | None = None,
        version: str | None = None,
    ):
        self.initial_state = initial_state
        references = [{"type": "metric", "id": "analytics.summary"}]
        await context.stream_service.publish_chunk(
            initial_state["task_id"],
            content="There were 12 NIL questions.",
        )
        yield (
            "updates",
            {
                "save_response": {
                    "completion_result": {
                        "status": "complete",
                        "task_id": initial_state["task_id"],
                        "session_id": initial_state["session_id"],
                        "assistant_message_id": initial_state["assistant_message_id"],
                        "answer_type": "analytics_answer",
                        "references": references,
                        "answer": "There were 12 NIL questions.",
                    }
                }
            },
        )


class NoopTitleExecutor:
    def __init__(self, **_: Any) -> None:
        pass

    async def execute(self, **_: Any) -> None:
        return None


class FakeConversationTitleExecutor:
    execute_calls: list[dict[str, Any]] = []

    def __init__(self, **_: Any) -> None:
        pass

    async def execute(self, **kwargs: Any) -> str:
        self.execute_calls.append({key: str(value) for key, value in kwargs.items()})
        return "NIL Deal Disclosure"


class FakeEngine:
    counter = 0

    def __init__(self, *, database_url: str, kwargs: dict[str, Any]) -> None:
        FakeEngine.counter += 1
        self.label = f"session-{FakeEngine.counter}"
        self.database_url = database_url
        self.kwargs = kwargs
        self.disposed = False

    async def dispose(self) -> None:
        self.disposed = True


class FakeSession:
    def __init__(self, engine: FakeEngine) -> None:
        self.label = engine.label

    async def __aenter__(self) -> "FakeSession":
        return self

    async def __aexit__(self, *args: Any) -> None:
        return None
