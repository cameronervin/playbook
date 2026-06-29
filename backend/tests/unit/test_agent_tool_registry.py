from __future__ import annotations

from app.agents.tools.tool_assignment import (
    build_prompt_bindings,
    build_workflow_chain_tool_map,
    resolve_active_tools,
)
from app.agents.tools.tool_prompts import ToolPromptKey
from app.agents.tools.tool_registry import (
    TOOL_REGISTRY,
    WORKFLOW_CHAIN_NAMES,
    ToolBuildContext,
)


def test_registry_declares_agent_tools() -> None:
    assert WORKFLOW_CHAIN_NAMES == {
        "athlete_chat": ("athlete_chat",),
        "dashboard_insights": ("dashboard_insights",),
    }

    specs = {spec.tool_name: spec for spec in TOOL_REGISTRY}

    kb_spec = specs["search_playbook_knowledgebase"]
    file_spec = specs["search_conversation_files"]
    metric_spec = specs["inspect_dashboard_metric"]
    examples_spec = specs["list_anonymized_query_examples"]
    assert kb_spec.workflow_chain_targets == {"athlete_chat": ("athlete_chat",)}
    assert file_spec.workflow_chain_targets == {"athlete_chat": ("athlete_chat",)}
    assert metric_spec.workflow_chain_targets == {
        "dashboard_insights": ("dashboard_insights",),
    }
    assert examples_spec.workflow_chain_targets == {
        "dashboard_insights": ("dashboard_insights",),
    }
    assert kb_spec.prompt_keys == (
        ToolPromptKey("athlete_chat", "search_playbook_knowledgebase"),
    )
    assert file_spec.prompt_keys == (
        ToolPromptKey("athlete_chat", "search_conversation_files"),
    )
    assert metric_spec.prompt_keys == (
        ToolPromptKey("dashboard_insights", "inspect_dashboard_metric"),
    )
    assert examples_spec.prompt_keys == (
        ToolPromptKey("dashboard_insights", "list_anonymized_query_examples"),
    )


def test_registry_builds_athlete_tools_without_build_time_source_registry(
    test_settings,
) -> None:
    context = ToolBuildContext(settings=test_settings)

    tools = resolve_active_tools(context)

    assert [tool.name for tool in tools] == [
        "search_playbook_knowledgebase",
        "search_conversation_files",
        "inspect_dashboard_metric",
        "list_anonymized_query_examples",
    ]
    assert not hasattr(context, "source_registries")
    assert not hasattr(context, "knowledgebase_provider")


def test_assignment_maps_athlete_kb_tool_to_athlete_chat(test_settings) -> None:
    context = ToolBuildContext(settings=test_settings)
    tools = resolve_active_tools(context)

    assignments = build_workflow_chain_tool_map(tools)

    assert [tool.name for tool in assignments["athlete_chat"]["athlete_chat"]] == [
        "search_playbook_knowledgebase",
        "search_conversation_files",
    ]
    assert [
        tool.name for tool in assignments["dashboard_insights"]["dashboard_insights"]
    ] == [
        "inspect_dashboard_metric",
        "list_anonymized_query_examples",
    ]


def test_prompt_bindings_include_tool_snippets_only_when_active() -> None:
    active = build_prompt_bindings(
        [
            "search_playbook_knowledgebase",
            "search_conversation_files",
            "inspect_dashboard_metric",
            "list_anonymized_query_examples",
        ]
    )
    inactive = build_prompt_bindings([])

    kb_key = ToolPromptKey("athlete_chat", "search_playbook_knowledgebase")
    file_key = ToolPromptKey("athlete_chat", "search_conversation_files")
    metric_key = ToolPromptKey("dashboard_insights", "inspect_dashboard_metric")
    examples_key = ToolPromptKey(
        "dashboard_insights",
        "list_anonymized_query_examples",
    )
    assert kb_key in active
    assert file_key in active
    assert metric_key in active
    assert examples_key in active
    assert "cited_source_keys" in active[kb_key]
    assert "uploaded" in active[file_key]
    assert "exact dashboard analytics counts" in active[metric_key]
    assert "anonymous user keys" in active[examples_key]
    assert inactive == {}
