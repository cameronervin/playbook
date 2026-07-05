from __future__ import annotations

from app.agents import builders
from app.agents.builders import chains_builder, graphs_builder
from app.agents.chains import (
    athlete_chat_chain,
    conversation_title_chain,
    dashboard_insights_chain,
)
from app.agents.context.prompt_composers.athlete_chat_prompt_composer import (
    build_athlete_chat_prompt,
)
from app.agents.nodes.athlete_chat import _sources_for_keys
from app.agents.prompts.conversation_title_prompt import (
    CONVERSATION_TITLE_SYSTEM_PROMPT,
)
from app.agents.runtime_context import (
    AthleteChatRuntimeContext,
    ConversationTitleRuntimeContext,
    DashboardInsightsRuntimeContext,
)
from app.agents.states.athlete_chat_state import AthleteChatState
from app.agents.states.conversation_title_state import ConversationTitleState
from app.agents.states.dashboard_insights_state import DashboardInsightsState
from app.agents.tools.knowledgebase import KnowledgebaseSource


class FakeChain:
    async def ainvoke(self, input: dict) -> dict:
        return {"structured_response": {"answer": "ok"}}


captured_chain_tool_names: list[str] = []


def _compact(text: str) -> str:
    return " ".join(text.split())


def fake_chain_factory(**_: object) -> FakeChain:
    captured_chain_tool_names[:] = [tool.name for tool in _.get("tools", [])]
    return FakeChain()


def test_create_athlete_chat_chain_wires_stateful_middleware(monkeypatch) -> None:
    captured_kwargs: dict[str, object] = {}

    def fake_create_agent(**kwargs: object) -> object:
        captured_kwargs.update(kwargs)
        return object()

    monkeypatch.setattr(athlete_chat_chain, "create_agent", fake_create_agent)

    result = athlete_chat_chain.create_athlete_chat_chain(
        chat_model=object(),
        tools=[],
    )

    middleware = captured_kwargs["middleware"]
    assert result is not None
    assert captured_kwargs["state_schema"] is AthleteChatState
    assert captured_kwargs["context_schema"] is AthleteChatRuntimeContext
    assert isinstance(middleware, list)
    assert len(middleware) == 1
    assert hasattr(middleware[0], "awrap_model_call")


def test_athlete_chat_prompt_includes_scope_refusal_and_grounding_policy() -> None:
    prompt = build_athlete_chat_prompt("athlete_chat")
    compact = _compact(prompt)

    assert "<tool_use_policy>" in prompt
    assert "Read the runtime context first" in prompt
    assert "Data tools are optional" in prompt
    assert "final structured response tool" in compact
    assert "Do not call the same search tool with equivalent arguments twice" in compact
    assert "After a relevant tool result" in prompt
    assert "only handles athletics-related questions" in prompt
    assert "politely refuse" in prompt
    assert "steer the athlete back to athletics" in prompt
    assert "NIL, compliance, recruiting" in prompt
    assert "retrieved Playbook knowledge base sources" in prompt


def test_athlete_kb_prompt_requires_returned_and_fresh_source_keys() -> None:
    prompt = build_athlete_chat_prompt(
        "athlete_chat",
        ["search_playbook_knowledgebase"],
    )
    compact = _compact(prompt)

    assert "Use only returned source keys" in prompt
    assert "cite the newest applicable source key" in prompt
    assert "do not cite stale conflict sources" in prompt
    assert "After this tool returns relevant official guidance" in compact
    assert "Do not call this tool again with equivalent arguments" in compact


def test_athlete_citation_selection_drops_stale_conflict_source() -> None:
    old_source = KnowledgebaseSource(
        source_key="S-old",
        source_title="Archived NIL Disclosure FAQ",
        text="Archived guidance should not be used when newer guidance applies.",
        metadata={
            "source_id": "src:nil-conflict-old-2025#chunk-1",
            "source_date": "2025-08-10",
            "metadata": {"category": "conflict_old"},
        },
    )
    new_source = KnowledgebaseSource(
        source_key="S-new",
        source_title="May 2026 NIL Disclosure Timing Update",
        text="This timing update supersedes prior FAQs.",
        metadata={
            "source_id": "src:nil-conflict-new-2026#chunk-1",
            "source_date": "2026-05-01",
            "metadata": {"category": "conflict_newer_source"},
        },
    )

    selected = _sources_for_keys(
        ["S-old", "S-new"],
        {"S-old": old_source, "S-new": new_source},
    )

    assert selected == [new_source]


def test_athlete_file_prompt_stops_when_no_ready_files_or_no_results() -> None:
    prompt = build_athlete_chat_prompt(
        "athlete_chat",
        ["search_conversation_files"],
    )
    compact = _compact(prompt)

    assert "Use this tool only when ready uploaded conversation files exist" in compact
    assert "If Ready conversation file count is 0, do not call this tool" in compact
    assert "After this tool returns relevant file excerpts" in compact
    assert "If this tool reports no ready files or no relevant file context" in compact
    assert "Do not call this tool again with equivalent arguments" in compact


def test_conversation_title_prompt_requires_canonical_eval_labels() -> None:
    prompt = CONVERSATION_TITLE_SYSTEM_PROMPT

    assert "<role>" in prompt
    assert "<rules>" in prompt
    assert "NIL disclosure" in prompt
    assert "recruiting" in prompt
    assert "emergency support" in prompt
    assert "travel receipts" in prompt
    assert "study hall" in prompt
    assert "contract approval" in prompt
    assert "ticket benefits" in prompt
    assert "3 to 7 words" in prompt
    assert "Never include private names" in prompt


def test_create_conversation_title_chain_wires_structured_agent(monkeypatch) -> None:
    captured_kwargs: dict[str, object] = {}

    def fake_create_agent(**kwargs: object) -> object:
        captured_kwargs.update(kwargs)
        return object()

    monkeypatch.setattr(conversation_title_chain, "create_agent", fake_create_agent)

    result = conversation_title_chain.create_conversation_title_chain(
        title_model=object(),
    )

    assert result is not None
    assert captured_kwargs["state_schema"] is ConversationTitleState
    assert captured_kwargs["context_schema"] is ConversationTitleRuntimeContext
    assert captured_kwargs["tools"] == []


def test_create_dashboard_insights_chain_wires_structured_agent(monkeypatch) -> None:
    captured_kwargs: dict[str, object] = {}

    def fake_create_agent(**kwargs: object) -> object:
        captured_kwargs.update(kwargs)
        return object()

    monkeypatch.setattr(dashboard_insights_chain, "create_agent", fake_create_agent)

    result = dashboard_insights_chain.create_dashboard_insights_chain(
        chat_model=object(),
        tools=[],
    )

    middleware = captured_kwargs["middleware"]
    assert result is not None
    assert captured_kwargs["state_schema"] is DashboardInsightsState
    assert captured_kwargs["context_schema"] is DashboardInsightsRuntimeContext
    assert captured_kwargs["tools"] == []
    assert isinstance(middleware, list)
    assert len(middleware) == 1
    assert hasattr(middleware[0], "awrap_model_call")


def test_agent_builder_exports_athlete_chat_and_title_without_example_graph() -> None:
    assert "compile_athlete_chat_graph" in builders.__all__
    assert "compile_conversation_title_graph" in builders.__all__
    assert "compile_dashboard_insights_graph" in builders.__all__
    assert "create_athlete_chat_node_set" in builders.__all__
    assert "create_conversation_title_node_set" in builders.__all__
    assert "create_dashboard_insights_node_set" in builders.__all__
    assert "build_athlete_chat_graph" not in builders.__all__
    assert "build_conversation_title_graph" not in builders.__all__
    assert "create_all_chains" not in builders.__all__
    assert "create_all_nodes" not in builders.__all__
    assert "compile_example_graph" not in builders.__all__
    assert "create_example_node_set" not in builders.__all__


def test_compile_athlete_chat_graph_builds_static_dependencies(
    test_settings,
    monkeypatch,
) -> None:
    original_create_nodes = graphs_builder.create_athlete_chat_node_set

    def spy_create_nodes(**kwargs: object) -> dict:
        assert "session" not in kwargs
        assert "stream_service" not in kwargs
        assert "source_registry" not in kwargs
        return original_create_nodes(**kwargs)  # type: ignore[arg-type]

    monkeypatch.setattr(
        chains_builder,
        "create_athlete_chat_chain",
        fake_chain_factory,
    )
    monkeypatch.setattr(
        graphs_builder,
        "create_athlete_chat_node_set",
        spy_create_nodes,
    )

    graph = graphs_builder.compile_athlete_chat_graph(
        chat_model=object(),
        checkpointer=None,
        app_settings=test_settings,
    )

    assert hasattr(graph, "astream")
    assert captured_chain_tool_names == [
        "search_playbook_knowledgebase",
        "search_conversation_files",
    ]
    assert not hasattr(graphs_builder, "ATHLETE_KB_TOOL_PROFILE")


def test_compile_conversation_title_graph_uses_title_dependencies(
    test_settings,
    monkeypatch,
) -> None:
    captured_models: list[object] = []

    def fake_title_chain_factory(**kwargs: object) -> FakeChain:
        captured_models.append(kwargs["title_model"])
        return FakeChain()

    monkeypatch.setattr(
        chains_builder,
        "create_conversation_title_chain",
        fake_title_chain_factory,
    )

    graph = graphs_builder.compile_conversation_title_graph(
        title_model="title-model",
        checkpointer=None,
        app_settings=test_settings,
    )

    assert hasattr(graph, "ainvoke")
    assert captured_models == ["title-model"]


def test_compile_dashboard_insights_graph_builds_static_dependencies(
    test_settings,
    monkeypatch,
) -> None:
    dashboard_tool_names: list[str] = []

    def fake_dashboard_chain_factory(**kwargs: object) -> FakeChain:
        dashboard_tool_names[:] = [tool.name for tool in kwargs.get("tools", [])]
        return FakeChain()

    monkeypatch.setattr(
        chains_builder,
        "create_dashboard_insights_chain",
        fake_dashboard_chain_factory,
    )

    graph = graphs_builder.compile_dashboard_insights_graph(
        chat_model=object(),
        checkpointer=None,
        app_settings=test_settings,
    )

    assert hasattr(graph, "ainvoke")
    assert dashboard_tool_names == [
        "inspect_dashboard_metric",
        "list_anonymized_query_examples",
    ]
