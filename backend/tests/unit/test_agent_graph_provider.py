from __future__ import annotations

from app.agents import graph_provider as graph_provider_module
from app.agents.graph_provider import AgentGraphProvider, AgentGraphProviderCache


def test_agent_graph_provider_reuses_compiled_graphs(test_settings, monkeypatch) -> None:
    athlete_calls = 0
    title_calls = 0
    dashboard_calls = 0
    athlete_graph = object()
    title_graph = object()
    dashboard_graph = object()

    def fake_compile_athlete_graph(**_: object) -> object:
        nonlocal athlete_calls
        athlete_calls += 1
        return athlete_graph

    def fake_compile_title_graph(**_: object) -> object:
        nonlocal title_calls
        title_calls += 1
        return title_graph

    def fake_compile_dashboard_graph(**_: object) -> object:
        nonlocal dashboard_calls
        dashboard_calls += 1
        return dashboard_graph

    monkeypatch.setattr(
        graph_provider_module,
        "compile_athlete_chat_graph",
        fake_compile_athlete_graph,
    )
    monkeypatch.setattr(
        graph_provider_module,
        "compile_conversation_title_graph",
        fake_compile_title_graph,
    )
    monkeypatch.setattr(
        graph_provider_module,
        "compile_dashboard_insights_graph",
        fake_compile_dashboard_graph,
    )

    provider = AgentGraphProvider(
        chat_model=object(),
        title_model=object(),
        settings=test_settings,
        checkpointer=object(),
    )

    assert provider.athlete_chat_graph() is athlete_graph
    assert provider.athlete_chat_graph() is athlete_graph
    assert provider.conversation_title_graph() is title_graph
    assert provider.conversation_title_graph() is title_graph
    assert provider.dashboard_insights_graph() is dashboard_graph
    assert provider.dashboard_insights_graph() is dashboard_graph
    assert athlete_calls == 1
    assert title_calls == 1
    assert dashboard_calls == 1


def test_agent_graph_provider_cache_reuses_provider_for_same_dependencies(
    test_settings,
) -> None:
    cache = AgentGraphProviderCache()
    chat_model = object()
    title_model = object()
    checkpointer = object()

    first = cache.get_or_create(
        chat_model=chat_model,
        title_model=title_model,
        settings=test_settings,
        checkpointer=checkpointer,
    )
    second = cache.get_or_create(
        chat_model=chat_model,
        title_model=title_model,
        settings=test_settings,
        checkpointer=checkpointer,
    )

    assert second is first


def test_agent_graph_provider_cache_replaces_provider_when_key_changes(
    test_settings,
) -> None:
    cache = AgentGraphProviderCache()
    chat_model = object()
    title_model = object()

    first = cache.get_or_create(
        chat_model=chat_model,
        title_model=title_model,
        settings=test_settings,
        checkpointer=object(),
    )
    second = cache.get_or_create(
        chat_model=chat_model,
        title_model=title_model,
        settings=test_settings,
        checkpointer=object(),
    )

    assert second is not first


def test_agent_graph_provider_cache_clear_resets_provider(test_settings) -> None:
    cache = AgentGraphProviderCache()
    chat_model = object()
    title_model = object()
    checkpointer = object()

    first = cache.get_or_create(
        chat_model=chat_model,
        title_model=title_model,
        settings=test_settings,
        checkpointer=checkpointer,
    )

    cache.clear()
    second = cache.get_or_create(
        chat_model=chat_model,
        title_model=title_model,
        settings=test_settings,
        checkpointer=checkpointer,
    )

    assert second is not first
