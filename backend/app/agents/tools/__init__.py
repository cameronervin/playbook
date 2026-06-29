"""Agent tools: declarative registry + runtime assignment."""

from app.agents.tools.admin_chat import (
    ADMIN_CHAT_DASHBOARD_INSIGHTS_TOOL_PROFILE,
    ADMIN_CHAT_METRIC_TOOL_PROFILE,
    ADMIN_CHAT_QUERY_EXAMPLES_TOOL_PROFILE,
    AdminChatToolProfile,
    create_admin_chat_dashboard_insights_tool,
    create_admin_chat_metric_tool,
    create_admin_chat_query_examples_tool,
)
from app.agents.tools.dashboard_insights import (
    DASHBOARD_INSIGHTS_METRIC_TOOL_PROFILE,
    DASHBOARD_INSIGHTS_QUERY_EXAMPLES_TOOL_PROFILE,
    DashboardInsightsToolProfile,
    create_dashboard_insights_metric_tool,
    create_dashboard_insights_query_examples_tool,
)
from app.agents.tools.knowledgebase import (
    ATHLETE_CONVERSATION_FILE_TOOL_PROFILE,
    ATHLETE_KB_TOOL_PROFILE,
    KnowledgebaseSource,
    KnowledgebaseToolProfile,
    conversation_file_search_context,
    create_conversation_file_search_tool,
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
    "ATHLETE_CONVERSATION_FILE_TOOL_PROFILE",
    "ATHLETE_KB_TOOL_PROFILE",
    "ADMIN_CHAT_DASHBOARD_INSIGHTS_TOOL_PROFILE",
    "ADMIN_CHAT_METRIC_TOOL_PROFILE",
    "ADMIN_CHAT_QUERY_EXAMPLES_TOOL_PROFILE",
    "DASHBOARD_INSIGHTS_METRIC_TOOL_PROFILE",
    "DASHBOARD_INSIGHTS_QUERY_EXAMPLES_TOOL_PROFILE",
    "ToolPromptKey",
    "ToolBuildContext",
    "ToolSpec",
    "ToolWorkflow",
    "AdminChatToolProfile",
    "DashboardInsightsToolProfile",
    "KnowledgebaseSource",
    "KnowledgebaseToolProfile",
    "build_prompt_bindings",
    "build_workflow_chain_tool_map",
    "conversation_file_search_context",
    "create_admin_chat_dashboard_insights_tool",
    "create_admin_chat_metric_tool",
    "create_admin_chat_query_examples_tool",
    "create_dashboard_insights_metric_tool",
    "create_dashboard_insights_query_examples_tool",
    "create_conversation_file_search_tool",
    "create_knowledgebase_search_tool",
    "resolve_active_tools",
]
