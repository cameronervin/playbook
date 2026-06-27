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


def test_registry_declares_athlete_chat_knowledgebase_tools() -> None:
    assert WORKFLOW_CHAIN_NAMES == {"athlete_chat": ("athlete_chat",)}

    specs = {spec.tool_name: spec for spec in TOOL_REGISTRY}

    kb_spec = specs["search_playbook_knowledgebase"]
    file_spec = specs["search_conversation_files"]
    assert kb_spec.workflow_chain_targets == {"athlete_chat": ("athlete_chat",)}
    assert file_spec.workflow_chain_targets == {"athlete_chat": ("athlete_chat",)}
    assert kb_spec.prompt_keys == (
        ToolPromptKey("athlete_chat", "search_playbook_knowledgebase"),
    )
    assert file_spec.prompt_keys == (
        ToolPromptKey("athlete_chat", "search_conversation_files"),
    )


def test_registry_builds_athlete_tools_without_build_time_source_registry(
    test_settings,
) -> None:
    context = ToolBuildContext(settings=test_settings)

    tools = resolve_active_tools(context)

    assert [tool.name for tool in tools] == [
        "search_playbook_knowledgebase",
        "search_conversation_files",
    ]
    assert not hasattr(context, "source_registries")
    assert not hasattr(context, "knowledgebase_provider")


def test_assignment_maps_athlete_kb_tool_to_athlete_chat(test_settings) -> None:
    context = ToolBuildContext(settings=test_settings)
    tools = resolve_active_tools(context)

    assignments = build_workflow_chain_tool_map(tools)

    assert assignments["athlete_chat"]["athlete_chat"] == tools


def test_prompt_bindings_include_athlete_kb_snippet_only_when_active() -> None:
    active = build_prompt_bindings(
        ["search_playbook_knowledgebase", "search_conversation_files"]
    )
    inactive = build_prompt_bindings([])

    kb_key = ToolPromptKey("athlete_chat", "search_playbook_knowledgebase")
    file_key = ToolPromptKey("athlete_chat", "search_conversation_files")
    assert kb_key in active
    assert file_key in active
    assert "cited_source_keys" in active[kb_key]
    assert "uploaded" in active[file_key]
    assert inactive == {}
