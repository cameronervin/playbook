"""Node-set construction for Playbook agent workflows."""

from __future__ import annotations

from typing import Any

from app.agents.nodes.admin_chat import create_admin_chat_nodes
from app.agents.nodes.athlete_chat import create_athlete_chat_nodes
from app.agents.nodes.conversation_title import create_conversation_title_nodes
from app.agents.nodes.dashboard_insights import create_dashboard_insights_nodes


def create_athlete_chat_node_set(
    *,
    chains: dict[str, Any],
) -> dict[str, Any]:
    """Create the node set for the athlete chat workflow."""
    return {
        "athlete_chat": create_athlete_chat_nodes(
            chains=chains,
        )
    }


def create_conversation_title_node_set(
    *,
    chains: dict[str, Any],
) -> dict[str, Any]:
    """Create the node set for the conversation title workflow."""
    return {
        "conversation_title": create_conversation_title_nodes(
            chains=chains,
        )
    }


def create_dashboard_insights_node_set(
    *,
    chains: dict[str, Any],
) -> dict[str, Any]:
    """Create the node set for the dashboard insights workflow."""
    return {
        "dashboard_insights": create_dashboard_insights_nodes(
            chains=chains,
        )
    }


def create_admin_chat_node_set(
    *,
    chains: dict[str, Any],
) -> dict[str, Any]:
    """Create the node set for the admin chat workflow."""
    return {
        "admin_chat": create_admin_chat_nodes(
            chains=chains,
        )
    }
