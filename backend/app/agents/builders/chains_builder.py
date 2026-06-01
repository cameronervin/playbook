"""Chain construction for the example workflow.

Pattern: the chains builder is where tools, prompts, and chains come together.
It (1) resolves the active tools from the registry, (2) composes per-chain
prompts with the active tools' snippets, (3) assigns tools to chains, and
(4) constructs each chain. The result is a ``{chain_name -> chain}`` dict the
nodes builder consumes.
"""

from __future__ import annotations

from typing import Any

from langchain_core.language_models import BaseChatModel

from app.agents.chains.example_chain import create_example_chain
from app.agents.context.prompt_composers.example_prompt_composer import (
    build_example_prompts,
)
from app.agents.tools.tool_assignment import (
    build_workflow_chain_tool_map,
    resolve_active_tools,
)
from app.core.config import settings


def create_example_chain_set(chat_model: BaseChatModel) -> dict[str, Any]:
    """Create the chains required by the example workflow."""
    tools = resolve_active_tools(settings)
    prompts = build_example_prompts([tool.name for tool in tools])
    example_chain_tools = build_workflow_chain_tool_map(tools).get("example", {})

    return {
        "example": create_example_chain(
            chat_model,
            tools=example_chain_tools.get("example", []),
            prompt=prompts["example"],
        ),
    }


def create_all_chains(chat_model: BaseChatModel) -> dict[str, Any]:
    """Create all chain sets for the agent subsystem (currently just example)."""
    return {**create_example_chain_set(chat_model)}
