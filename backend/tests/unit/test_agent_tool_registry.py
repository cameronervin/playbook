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
        "admin_chat": ("admin_chat",),
    }

    specs = {spec.tool_name: spec for spec in TOOL_REGISTRY}

    kb_spec = specs["search_playbook_knowledgebase"]
    file_spec = specs["search_conversation_files"]
    metric_spec = specs["inspect_dashboard_metric"]
    examples_spec = specs["list_anonymized_query_examples"]
    admin_metric_spec = specs["inspect_admin_metric"]
    admin_queries_spec = specs["list_anonymized_queries"]
    admin_insights_spec = specs["list_dashboard_insights"]
    assert kb_spec.workflow_chain_targets == {"athlete_chat": ("athlete_chat",)}
    assert file_spec.workflow_chain_targets == {"athlete_chat": ("athlete_chat",)}
    assert metric_spec.workflow_chain_targets == {
        "dashboard_insights": ("dashboard_insights",),
    }
    assert examples_spec.workflow_chain_targets == {
        "dashboard_insights": ("dashboard_insights",),
    }
    assert admin_metric_spec.workflow_chain_targets == {
        "admin_chat": ("admin_chat",),
    }
    assert admin_queries_spec.workflow_chain_targets == {
        "admin_chat": ("admin_chat",),
    }
    assert admin_insights_spec.workflow_chain_targets == {
        "admin_chat": ("admin_chat",),
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
    assert admin_metric_spec.prompt_keys == (
        ToolPromptKey("admin_chat", "inspect_admin_metric"),
    )
    assert admin_queries_spec.prompt_keys == (
        ToolPromptKey("admin_chat", "list_anonymized_queries"),
    )
    assert admin_insights_spec.prompt_keys == (
        ToolPromptKey("admin_chat", "list_dashboard_insights"),
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
        "inspect_admin_metric",
        "list_anonymized_queries",
        "list_dashboard_insights",
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
    assert [tool.name for tool in assignments["admin_chat"]["admin_chat"]] == [
        "inspect_admin_metric",
        "list_anonymized_queries",
        "list_dashboard_insights",
    ]


def test_prompt_bindings_include_tool_snippets_only_when_active() -> None:
    active = build_prompt_bindings(
        [
            "search_playbook_knowledgebase",
            "search_conversation_files",
            "inspect_dashboard_metric",
            "list_anonymized_query_examples",
            "inspect_admin_metric",
            "list_anonymized_queries",
            "list_dashboard_insights",
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
    admin_metric_key = ToolPromptKey("admin_chat", "inspect_admin_metric")
    admin_queries_key = ToolPromptKey("admin_chat", "list_anonymized_queries")
    admin_insights_key = ToolPromptKey("admin_chat", "list_dashboard_insights")
    assert kb_key in active
    assert file_key in active
    assert metric_key in active
    assert examples_key in active
    assert admin_metric_key in active
    assert admin_queries_key in active
    assert admin_insights_key in active
    assert "cited_source_keys" in active[kb_key]
    assert "uploaded" in active[file_key]
    assert "exact dashboard analytics counts" in active[metric_key]
    assert "anonymous user keys" in active[examples_key]
    assert "query volume" in active[admin_metric_key]
    assert "anonymized message IDs" in active[admin_queries_key]
    assert "completed dashboard insight outputs" in active[admin_insights_key]
    assert inactive == {}
