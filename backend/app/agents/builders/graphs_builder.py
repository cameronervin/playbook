"""Graph compilation for Playbook agent workflows."""

from __future__ import annotations

from typing import Any

import structlog
from langchain_core.language_models import BaseChatModel
from langgraph.checkpoint.base import BaseCheckpointSaver

from app.agents.builders.chains_builder import (
    create_admin_chat_chain_set,
    create_athlete_chat_chain_set,
    create_conversation_title_chain_set,
    create_dashboard_insights_chain_set,
)
from app.agents.builders.nodes_builder import (
    create_admin_chat_node_set,
    create_athlete_chat_node_set,
    create_conversation_title_node_set,
    create_dashboard_insights_node_set,
)
from app.agents.graphs.admin_chat_graph import create_admin_chat_graph
from app.agents.graphs.athlete_chat_graph import create_athlete_chat_graph
from app.agents.graphs.conversation_title_graph import create_conversation_title_graph
from app.agents.graphs.dashboard_insights_graph import create_dashboard_insights_graph
from app.agents.tools.tool_assignment import (
    build_workflow_chain_tool_map,
    resolve_active_tools,
)
from app.agents.tools.tool_registry import (
    ToolBuildContext,
)
from app.core.config import Settings

logger = structlog.get_logger(__name__)


def compose_athlete_chat_dependencies(
    *,
    chat_model: BaseChatModel,
    app_settings: Settings,
) -> dict[str, Any]:
    """Create the athlete chat workflow's tools, chains, and nodes."""
    tool_context = ToolBuildContext(
        settings=app_settings,
    )
    active_tools = resolve_active_tools(tool_context)
    chain_tool_map = build_workflow_chain_tool_map(active_tools)
    athlete_tools = chain_tool_map["athlete_chat"]["athlete_chat"]
    chains = create_athlete_chat_chain_set(
        chat_model=chat_model,
        tools=athlete_tools,
        settings=app_settings,
    )
    logger.info("agent_chains_created", count=len(chains), scope="athlete_chat")
    nodes = create_athlete_chat_node_set(
        chains=chains,
    )
    logger.info("agent_nodes_created", count=len(nodes), scope="athlete_chat")
    return nodes


def compose_conversation_title_dependencies(
    *,
    title_model: BaseChatModel,
    app_settings: Settings,
) -> dict[str, Any]:
    """Create the conversation title workflow's chains and nodes."""
    chains = create_conversation_title_chain_set(
        title_model=title_model,
        settings=app_settings,
    )
    logger.info("agent_chains_created", count=len(chains), scope="conversation_title")
    nodes = create_conversation_title_node_set(
        chains=chains,
    )
    logger.info("agent_nodes_created", count=len(nodes), scope="conversation_title")
    return nodes


def compose_dashboard_insights_dependencies(
    *,
    chat_model: BaseChatModel,
    app_settings: Settings,
) -> dict[str, Any]:
    """Create the dashboard insights workflow's tools, chains, and nodes."""
    tool_context = ToolBuildContext(settings=app_settings)
    active_tools = resolve_active_tools(tool_context)
    chain_tool_map = build_workflow_chain_tool_map(active_tools)
    dashboard_tools = chain_tool_map["dashboard_insights"]["dashboard_insights"]
    chains = create_dashboard_insights_chain_set(
        chat_model=chat_model,
        tools=dashboard_tools,
        settings=app_settings,
    )
    logger.info("agent_chains_created", count=len(chains), scope="dashboard_insights")
    nodes = create_dashboard_insights_node_set(chains=chains)
    logger.info("agent_nodes_created", count=len(nodes), scope="dashboard_insights")
    return nodes


def compose_admin_chat_dependencies(
    *,
    chat_model: BaseChatModel,
    app_settings: Settings,
) -> dict[str, Any]:
    """Create the admin chat workflow's tools, chains, and nodes."""
    tool_context = ToolBuildContext(settings=app_settings)
    active_tools = resolve_active_tools(tool_context)
    chain_tool_map = build_workflow_chain_tool_map(active_tools)
    admin_chat_tools = chain_tool_map["admin_chat"]["admin_chat"]
    chains = create_admin_chat_chain_set(
        chat_model=chat_model,
        tools=admin_chat_tools,
        settings=app_settings,
    )
    logger.info("agent_chains_created", count=len(chains), scope="admin_chat")
    nodes = create_admin_chat_node_set(chains=chains)
    logger.info("agent_nodes_created", count=len(nodes), scope="admin_chat")
    return nodes


def compile_athlete_chat_graph(
    *,
    chat_model: BaseChatModel,
    checkpointer: BaseCheckpointSaver | None,
    app_settings: Settings,
):
    """Build and compile the athlete chat graph."""
    nodes = compose_athlete_chat_dependencies(
        chat_model=chat_model,
        app_settings=app_settings,
    )
    graph_builder = create_athlete_chat_graph(
        nodes=nodes["athlete_chat"],
    )
    return graph_builder.compile(checkpointer=checkpointer)


def compile_conversation_title_graph(
    *,
    title_model: BaseChatModel,
    checkpointer: BaseCheckpointSaver | None,
    app_settings: Settings,
):
    """Build and compile the conversation title graph."""
    nodes = compose_conversation_title_dependencies(
        title_model=title_model,
        app_settings=app_settings,
    )
    graph_builder = create_conversation_title_graph(
        nodes=nodes["conversation_title"],
    )
    return graph_builder.compile(checkpointer=checkpointer)


def compile_dashboard_insights_graph(
    *,
    chat_model: BaseChatModel,
    checkpointer: BaseCheckpointSaver | None,
    app_settings: Settings,
):
    """Build and compile the dashboard insights graph."""
    nodes = compose_dashboard_insights_dependencies(
        chat_model=chat_model,
        app_settings=app_settings,
    )
    graph_builder = create_dashboard_insights_graph(
        nodes=nodes["dashboard_insights"],
    )
    return graph_builder.compile(checkpointer=checkpointer)


def compile_admin_chat_graph(
    *,
    chat_model: BaseChatModel,
    checkpointer: BaseCheckpointSaver | None,
    app_settings: Settings,
):
    """Build and compile the admin chat graph."""
    nodes = compose_admin_chat_dependencies(
        chat_model=chat_model,
        app_settings=app_settings,
    )
    graph_builder = create_admin_chat_graph(
        nodes=nodes["admin_chat"],
    )
    return graph_builder.compile(checkpointer=checkpointer)
