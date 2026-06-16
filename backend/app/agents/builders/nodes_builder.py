"""Node-set construction for Playbook agent workflows."""

from __future__ import annotations

from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.nodes.athlete_chat import create_athlete_chat_nodes
from app.agents.tools.knowledgebase import SourceRegistry
from app.core.config import Settings
from app.infrastructure.knowledgebase import BaseKnowledgebaseProvider
from app.services.agent_stream_service import AgentStreamService


def create_athlete_chat_node_set(
    *,
    chains: dict[str, Any],
    session: AsyncSession,
    settings: Settings,
    stream_service: AgentStreamService,
    source_registry: SourceRegistry,
    knowledgebase_provider: BaseKnowledgebaseProvider,
) -> dict[str, Any]:
    """Create the node set for the athlete chat workflow."""
    return {
        "athlete_chat": create_athlete_chat_nodes(
            chains=chains,
            session=session,
            settings=settings,
            stream_service=stream_service,
            source_registry=source_registry,
            knowledgebase_provider=knowledgebase_provider,
        )
    }


def create_all_nodes(
    *,
    chains: dict[str, Any],
    session: AsyncSession,
    settings: Settings,
    stream_service: AgentStreamService,
    source_registry: SourceRegistry,
    knowledgebase_provider: BaseKnowledgebaseProvider,
) -> dict[str, Any]:
    """Create all node sets for the active agent subsystem."""
    return {
        **create_athlete_chat_node_set(
            chains=chains,
            session=session,
            settings=settings,
            stream_service=stream_service,
            source_registry=source_registry,
            knowledgebase_provider=knowledgebase_provider,
        )
    }
