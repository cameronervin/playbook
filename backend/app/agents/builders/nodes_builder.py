"""Node-set construction for the example workflow.

Pattern: the nodes builder takes the chains dict and infrastructure handles
(session factory, storage) and produces the ``{node_name -> node_fn}`` dict the
graph registers. It keeps node wiring out of both the chains builder and the
graph topology.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from app.agents.nodes.example.chains import create_example_nodes
from app.infrastructure.storage import StorageProvider


def create_example_node_set(
    *,
    chains: dict[str, Any],
    get_session: Callable,
    storage: StorageProvider | None = None,
) -> dict[str, Any]:
    """Create the node set for the example workflow.

    ``storage`` is accepted to mirror the production signature (some nodes need
    blob storage); the example nodes don't use it yet.
    """
    return {
        "example": create_example_nodes(
            chains=chains,
            get_session=get_session,
        )
    }


def create_all_nodes(
    *,
    chains: dict[str, Any],
    get_session: Callable,
    storage: StorageProvider | None = None,
) -> dict[str, Any]:
    """Create all node sets for the agent subsystem (currently just example)."""
    return {
        **create_example_node_set(
            chains=chains,
            get_session=get_session,
            storage=storage,
        )
    }
