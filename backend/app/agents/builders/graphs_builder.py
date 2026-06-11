"""Graph compilation for the example workflow.

Pattern: the graphs builder ties everything together. It composes shared
chain/node dependencies once, then compiles the topology with a checkpointer.
``compile_example_graph`` is the single public entry point main.py calls at
startup.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

import structlog
from langchain_core.language_models import BaseChatModel
from langgraph.checkpoint.base import BaseCheckpointSaver

from app.agents.builders.chains_builder import create_example_chain_set
from app.agents.builders.nodes_builder import create_example_node_set
from app.agents.graphs.example_graph import create_example_graph
from app.core.config import Settings
from app.infrastructure.storage import StorageProvider

logger = structlog.get_logger(__name__)


@dataclass(frozen=True, slots=True)
class GraphDependencies:
    """Reusable chain/node maps shared across graph compilation."""

    chains: dict[str, Any]
    nodes: dict[str, Any]


def compose_example_dependencies(
    *,
    chat_model: BaseChatModel,
    get_session: Callable,
    app_settings: Settings,
    storage: StorageProvider | None = None,
) -> GraphDependencies:
    """Create the example workflow's chains and nodes."""
    chains = create_example_chain_set(chat_model, app_settings=app_settings)
    logger.info("agent_chains_created", count=len(chains), scope="example")
    nodes = create_example_node_set(
        chains=chains,
        get_session=get_session,
        settings=app_settings,
        storage=storage,
    )
    logger.info("agent_nodes_created", count=len(nodes), scope="example")
    return GraphDependencies(chains=chains, nodes=nodes)


def compile_example_graph(
    *,
    chat_model: BaseChatModel,
    get_session: Callable,
    checkpointer: BaseCheckpointSaver,
    app_settings: Settings,
    storage: StorageProvider | None = None,
):
    """Build and compile the example graph (public entry point for main.py).

    Args:
        chat_model: LangChain chat model from the LLM provider.
        get_session: Async session-factory dependency (e.g. ``get_db``).
        checkpointer: LangGraph checkpointer for state persistence.
        storage: Optional blob storage provider.

    Returns:
        A compiled LangGraph ready for ``ExampleExecutor``.
    """
    dependencies = compose_example_dependencies(
        chat_model=chat_model,
        get_session=get_session,
        app_settings=app_settings,
        storage=storage,
    )
    graph_builder = create_example_graph(nodes=dependencies.nodes["example"])
    return graph_builder.compile(checkpointer=checkpointer)


def build_example_graph(
    chat_model: BaseChatModel,
    get_session: Callable,
    checkpointer: BaseCheckpointSaver,
    app_settings: Settings,
    storage: StorageProvider | None = None,
):
    """Positional-arg convenience wrapper around ``compile_example_graph``."""
    return compile_example_graph(
        chat_model=chat_model,
        get_session=get_session,
        checkpointer=checkpointer,
        app_settings=app_settings,
        storage=storage,
    )
