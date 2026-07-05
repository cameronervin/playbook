"""Graph nodes for agent workflows."""

from app.agents.nodes.admin_chat import create_admin_chat_nodes
from app.agents.nodes.athlete_chat import create_athlete_chat_nodes
from app.agents.nodes.conversation_title import create_conversation_title_nodes
from app.agents.nodes.dashboard_insights import create_dashboard_insights_nodes

__all__ = [
    "create_athlete_chat_nodes",
    "create_admin_chat_nodes",
    "create_conversation_title_nodes",
    "create_dashboard_insights_nodes",
]
