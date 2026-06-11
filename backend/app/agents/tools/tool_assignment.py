"""Runtime tool assignment from the declarative tool registry.

Pattern: at startup the builders call ``resolve_active_tools(settings)`` to
instantiate every enabled tool once, then ``build_workflow_chain_tool_map`` to
assign each tool to the chains its ``ToolSpec`` targets. Prompt snippets are
resolved separately via ``build_prompt_bindings``.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping

from langchain_core.tools import BaseTool

from app.agents.tools.tool_prompts import TOOL_PROMPT_REGISTRY, ToolPromptKey
from app.agents.tools.tool_registry import (
    TOOL_REGISTRY,
    WORKFLOW_CHAIN_NAMES,
    ToolSpec,
    ToolWorkflow,
)

WorkflowChainToolMap = dict[ToolWorkflow, dict[str, list[BaseTool]]]


def resolve_active_tools(
    config: object,
    registry: Iterable[ToolSpec] = TOOL_REGISTRY,
) -> list[BaseTool]:
    """Build all enabled tools in stable registry order."""
    tools: list[BaseTool] = []
    for spec in registry:
        if spec.enabled_predicate(config):
            tools.append(spec.factory(config))
    return tools


def build_workflow_chain_tool_map(
    active_tools: list[BaseTool],
    registry: Iterable[ToolSpec] = TOOL_REGISTRY,
) -> WorkflowChainToolMap:
    """Assign active tools to their workflow/chain targets."""
    tool_by_name = {tool.name: tool for tool in active_tools}
    assignments: WorkflowChainToolMap = {
        workflow: {chain: [] for chain in chains}
        for workflow, chains in WORKFLOW_CHAIN_NAMES.items()
    }

    for spec in registry:
        tool = tool_by_name.get(spec.tool_name)
        if tool is None:
            continue
        for workflow, chains in spec.workflow_chain_targets.items():
            chain_map = assignments.setdefault(workflow, {})
            for chain_name in chains:
                chain_map.setdefault(chain_name, []).append(tool)

    return assignments


def build_prompt_bindings(
    active_tool_names: Iterable[str],
    registry: Iterable[ToolSpec] = TOOL_REGISTRY,
    prompt_registry: Mapping[ToolPromptKey, str] = TOOL_PROMPT_REGISTRY,
) -> dict[ToolPromptKey, str]:
    """Resolve active prompt snippets keyed by chain/tool pair."""
    active = set(active_tool_names)
    bindings: dict[ToolPromptKey, str] = {}
    for spec in registry:
        if spec.tool_name not in active:
            continue
        for prompt_key in spec.prompt_keys:
            snippet = prompt_registry.get(prompt_key)
            if snippet:
                bindings[prompt_key] = snippet
    return bindings
