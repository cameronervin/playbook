"""Agent tools: declarative registry + runtime assignment."""

from app.agents.tools.knowledgebase import (
    ATHLETE_KB_TOOL_PROFILE,
    KnowledgebaseSource,
    KnowledgebaseToolProfile,
    create_knowledgebase_search_tool,
)
from app.agents.tools.tool_assignment import (
    build_prompt_bindings,
    build_workflow_chain_tool_map,
    resolve_active_tools,
)
from app.agents.tools.tool_prompts import TOOL_PROMPT_REGISTRY, ToolPromptKey
from app.agents.tools.tool_registry import (
    TOOL_REGISTRY,
    WORKFLOW_CHAIN_NAMES,
    ToolBuildContext,
    ToolSpec,
    ToolWorkflow,
)

__all__ = [
    "TOOL_PROMPT_REGISTRY",
    "TOOL_REGISTRY",
    "WORKFLOW_CHAIN_NAMES",
    "ATHLETE_KB_TOOL_PROFILE",
    "ToolPromptKey",
    "ToolBuildContext",
    "ToolSpec",
    "ToolWorkflow",
    "KnowledgebaseSource",
    "KnowledgebaseToolProfile",
    "build_prompt_bindings",
    "build_workflow_chain_tool_map",
    "create_knowledgebase_search_tool",
    "resolve_active_tools",
]
