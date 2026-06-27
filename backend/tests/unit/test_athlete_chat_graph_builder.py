from __future__ import annotations

from app.agents import builders
from app.agents.builders import chains_builder, graphs_builder
from app.agents.chains import athlete_chat_chain, conversation_title_chain
from app.agents.runtime_context import (
    AthleteChatRuntimeContext,
    ConversationTitleRuntimeContext,
)
from app.agents.states.athlete_chat_state import AthleteChatState
from app.agents.states.conversation_title_state import ConversationTitleState


class FakeChain:
    async def ainvoke(self, input: dict) -> dict:
        return {"structured_response": {"answer": "ok"}}


captured_chain_tool_names: list[str] = []


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


def test_agent_builder_exports_athlete_chat_and_title_without_example_graph() -> None:
    assert "compile_athlete_chat_graph" in builders.__all__
    assert "compile_conversation_title_graph" in builders.__all__
    assert "create_athlete_chat_node_set" in builders.__all__
    assert "create_conversation_title_node_set" in builders.__all__
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
