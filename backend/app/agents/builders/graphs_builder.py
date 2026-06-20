"""Graph compilation for Playbook agent workflows."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import structlog
from langchain_core.language_models import BaseChatModel
from langgraph.checkpoint.base import BaseCheckpointSaver
from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.builders.chains_builder import (
    create_athlete_chat_chain_set,
    create_conversation_title_chain_set,
)
from app.agents.builders.nodes_builder import (
    create_athlete_chat_node_set,
    create_conversation_title_node_set,
)
from app.agents.graphs.athlete_chat_graph import create_athlete_chat_graph
from app.agents.graphs.conversation_title_graph import create_conversation_title_graph
from app.agents.tools.knowledgebase import (
    SourceRegistry,
)
from app.agents.tools.tool_assignment import (
    build_workflow_chain_tool_map,
    resolve_active_tools,
)
from app.agents.tools.tool_registry import (
    ATHLETE_CHAT_SOURCE_REGISTRY_KEY,
    ToolBuildContext,
)
from app.core.config import Settings
from app.infrastructure.knowledgebase import BaseKnowledgebaseProvider
from app.services.agent_stream_service import AgentStreamService

logger = structlog.get_logger(__name__)


@dataclass(frozen=True, slots=True)
class GraphDependencies:
    """Reusable chain/node maps shared across graph compilation."""

    chains: dict[str, Any]
    nodes: dict[str, Any]
    source_registry: SourceRegistry


def compose_athlete_chat_dependencies(
    *,
    chat_model: BaseChatModel,
    session: AsyncSession,
    knowledgebase_provider: BaseKnowledgebaseProvider,
    stream_service: AgentStreamService,
    app_settings: Settings,
) -> GraphDependencies:
    """Create the athlete chat workflow's tools, chains, and nodes."""
    tool_context = ToolBuildContext(
        settings=app_settings,
        knowledgebase_provider=knowledgebase_provider,
    )
    active_tools = resolve_active_tools(tool_context)
    chain_tool_map = build_workflow_chain_tool_map(active_tools)
    athlete_tools = chain_tool_map["athlete_chat"]["athlete_chat"]
    source_registry = tool_context.source_registries.get(
        ATHLETE_CHAT_SOURCE_REGISTRY_KEY,
        {},
    )
    chains = create_athlete_chat_chain_set(
        chat_model=chat_model,
        tools=athlete_tools,
        settings=app_settings,
    )
    logger.info("agent_chains_created", count=len(chains), scope="athlete_chat")
    nodes = create_athlete_chat_node_set(
        chains=chains,
        session=session,
        settings=app_settings,
        stream_service=stream_service,
        source_registry=source_registry,
        knowledgebase_provider=knowledgebase_provider,
    )
    logger.info("agent_nodes_created", count=len(nodes), scope="athlete_chat")
    return GraphDependencies(
        chains=chains,
        nodes=nodes,
        source_registry=source_registry,
    )


def compose_conversation_title_dependencies(
    *,
    title_model: BaseChatModel,
    session: AsyncSession,
    app_settings: Settings,
) -> GraphDependencies:
    """Create the conversation title workflow's chains and nodes."""
    chains = create_conversation_title_chain_set(
        title_model=title_model,
        settings=app_settings,
    )
    logger.info("agent_chains_created", count=len(chains), scope="conversation_title")
    nodes = create_conversation_title_node_set(
        chains=chains,
        session=session,
        settings=app_settings,
    )
    logger.info("agent_nodes_created", count=len(nodes), scope="conversation_title")
    return GraphDependencies(
        chains=chains,
        nodes=nodes,
        source_registry={},
    )


def compile_athlete_chat_graph(
    *,
    chat_model: BaseChatModel,
    session: AsyncSession,
    knowledgebase_provider: BaseKnowledgebaseProvider,
    stream_service: AgentStreamService,
    checkpointer: BaseCheckpointSaver | None,
    app_settings: Settings,
):
    """Build and compile the athlete chat graph."""
    dependencies = compose_athlete_chat_dependencies(
        chat_model=chat_model,
        session=session,
        knowledgebase_provider=knowledgebase_provider,
        stream_service=stream_service,
        app_settings=app_settings,
    )
    graph_builder = create_athlete_chat_graph(
        nodes=dependencies.nodes["athlete_chat"],
    )
    return graph_builder.compile(checkpointer=checkpointer)


def compile_conversation_title_graph(
    *,
    title_model: BaseChatModel,
    session: AsyncSession,
    checkpointer: BaseCheckpointSaver | None,
    app_settings: Settings,
):
    """Build and compile the conversation title graph."""
    dependencies = compose_conversation_title_dependencies(
        title_model=title_model,
        session=session,
        app_settings=app_settings,
    )
    graph_builder = create_conversation_title_graph(
        nodes=dependencies.nodes["conversation_title"],
    )
    return graph_builder.compile(checkpointer=checkpointer)


def build_athlete_chat_graph(
    chat_model: BaseChatModel,
    session: AsyncSession,
    knowledgebase_provider: BaseKnowledgebaseProvider,
    stream_service: AgentStreamService,
    checkpointer: BaseCheckpointSaver | None,
    app_settings: Settings,
):
    """Positional-arg convenience wrapper around ``compile_athlete_chat_graph``."""
    return compile_athlete_chat_graph(
        chat_model=chat_model,
        session=session,
        knowledgebase_provider=knowledgebase_provider,
        stream_service=stream_service,
        checkpointer=checkpointer,
        app_settings=app_settings,
    )


def build_conversation_title_graph(
    title_model: BaseChatModel,
    session: AsyncSession,
    checkpointer: BaseCheckpointSaver | None,
    app_settings: Settings,
):
    """Positional-arg convenience wrapper around title graph compilation."""
    return compile_conversation_title_graph(
        title_model=title_model,
        session=session,
        checkpointer=checkpointer,
        app_settings=app_settings,
    )
