"""LangGraph topology for the Playbook athlete chat workflow."""

from __future__ import annotations

from typing import Literal

from langgraph.graph import END, START, StateGraph

from app.agents.states.athlete_chat_state import AthleteChatState


def create_athlete_chat_graph(nodes: dict[str, object]) -> StateGraph:
    """Create the athlete chat graph topology without compiling it."""
    builder = StateGraph(AthleteChatState)
    for name, node_fn in nodes.items():
        builder.add_node(name, node_fn)

    builder.add_edge(START, "load_state")
    builder.add_edge("load_state", "safety_check")
    builder.add_conditional_edges(
        "safety_check",
        _route_after_safety,
        {
            "prepare_conversation_file_snippets": "prepare_conversation_file_snippets",
            "save_state": "save_state",
        },
    )
    builder.add_edge("prepare_conversation_file_snippets", "run_agent")
    builder.add_edge("run_agent", "save_state")
    builder.add_edge("save_state", END)
    return builder


def _route_after_safety(
    state: AthleteChatState,
) -> Literal["prepare_conversation_file_snippets", "save_state"]:
    if state.get("should_bypass_agent", False):
        return "save_state"
    return "prepare_conversation_file_snippets"
