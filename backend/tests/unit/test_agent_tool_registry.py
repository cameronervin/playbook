from __future__ import annotations

from app.agents.tools.tool_assignment import (
    build_prompt_bindings,
    build_workflow_chain_tool_map,
    resolve_active_tools,
)
from app.agents.tools.tool_prompts import ToolPromptKey
from app.agents.tools.tool_registry import (
    TOOL_REGISTRY,
    ToolBuildContext,
    WORKFLOW_CHAIN_NAMES,
)
from app.schemas.knowledgebase import KnowledgebaseResult


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
            context="",
            sources=[],
            zero_hit=True,
            latency_ms=1,
        )


def test_registry_declares_athlete_chat_knowledgebase_tool() -> None:
    assert WORKFLOW_CHAIN_NAMES == {"athlete_chat": ("athlete_chat",)}

    spec = next(
        spec for spec in TOOL_REGISTRY if spec.tool_name == "search_playbook_knowledgebase"
    )

    assert spec.workflow_chain_targets == {"athlete_chat": ("athlete_chat",)}
    assert spec.prompt_keys == (
        ToolPromptKey("athlete_chat", "search_playbook_knowledgebase"),
    )


def test_registry_builds_athlete_kb_tool_and_source_registry(test_settings) -> None:
    context = ToolBuildContext(
        settings=test_settings,
        knowledgebase_provider=FakeKnowledgebaseProvider(),
    )

    tools = resolve_active_tools(context)

    assert [tool.name for tool in tools] == ["search_playbook_knowledgebase"]
    assert "search_playbook_knowledgebase" in context.source_registries
    assert context.source_registries["search_playbook_knowledgebase"] == {}


def test_assignment_maps_athlete_kb_tool_to_athlete_chat(test_settings) -> None:
    context = ToolBuildContext(
        settings=test_settings,
        knowledgebase_provider=FakeKnowledgebaseProvider(),
    )
    tools = resolve_active_tools(context)

    assignments = build_workflow_chain_tool_map(tools)

    assert assignments["athlete_chat"]["athlete_chat"] == tools


def test_prompt_bindings_include_athlete_kb_snippet_only_when_active() -> None:
    active = build_prompt_bindings(["search_playbook_knowledgebase"])
    inactive = build_prompt_bindings([])

    key = ToolPromptKey("athlete_chat", "search_playbook_knowledgebase")
    assert key in active
    assert "cited_source_keys" in active[key]
    assert inactive == {}
