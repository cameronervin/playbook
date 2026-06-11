from __future__ import annotations

from app.agents import builders
from app.agents.builders import chains_builder, graphs_builder
from app.agents.chains import athlete_chat_chain
from app.agents.states.athlete_chat_state import AthleteChatState
from app.infrastructure.streaming import InMemoryAgentStreamProvider
from app.services.agent_stream_service import AgentStreamService


class FakeKnowledgebaseProvider:
    provider_name = "fake"


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
    assert isinstance(middleware, list)
    assert len(middleware) == 1
    assert hasattr(middleware[0], "awrap_model_call")


def test_agent_builder_exports_athlete_chat_without_example_graph() -> None:
    assert "compile_athlete_chat_graph" in builders.__all__
    assert "create_athlete_chat_node_set" in builders.__all__
    assert "compile_example_graph" not in builders.__all__
    assert "create_example_node_set" not in builders.__all__


def test_compile_athlete_chat_graph_uses_injected_dependencies(
    test_settings,
    monkeypatch,
) -> None:
    captured_source_registries: list[dict] = []
    original_create_nodes = graphs_builder.create_athlete_chat_node_set

    def spy_create_nodes(**kwargs: object) -> dict:
        captured_source_registries.append(kwargs["source_registry"])  # type: ignore[arg-type]
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
        session=object(),
        knowledgebase_provider=FakeKnowledgebaseProvider(),
        stream_service=AgentStreamService(InMemoryAgentStreamProvider()),
        checkpointer=None,
        app_settings=test_settings,
    )

    assert hasattr(graph, "astream")
    assert captured_chain_tool_names == ["search_playbook_knowledgebase"]
    assert captured_source_registries == [{}]
    assert not hasattr(graphs_builder, "ATHLETE_KB_TOOL_PROFILE")
