"""Declarative registry of chain-scoped agent tools.

Pattern: tools are declared once as frozen ``ToolSpec`` rows in ``TOOL_REGISTRY``.
Each spec carries:
    - a ``factory`` that builds the LangChain tool,
    - an ``enabled_predicate`` evaluated against ``settings`` at startup,
    - ``workflow_chain_targets`` mapping a workflow -> the chains that receive it,
    - optional ``prompt_keys`` linking the tool to its prompt snippets.

To add a tool: write a factory, then append one ``ToolSpec`` here. Runtime
assignment (``tool_assignment.py``) and prompt composition pick it up
automatically — no graph or builder changes required.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from typing import Literal

import structlog
from langchain_core.tools import BaseTool

from app.agents.tools.example_kb_tool import create_example_kb_tool
from app.agents.tools.tool_prompts import ToolPromptKey
from app.infrastructure.knowledgebase import is_kb_feature_enabled

logger = structlog.get_logger(__name__)

# The set of workflows in the scaffold. Add new workflow literals here.
ToolWorkflow = Literal["example"]

# Chain names per workflow. The example workflow has a single chain: "example".
EXAMPLE_CHAIN_NAMES: tuple[str, ...] = ("example",)

WORKFLOW_CHAIN_NAMES: dict[ToolWorkflow, tuple[str, ...]] = {
    "example": EXAMPLE_CHAIN_NAMES,
}


@dataclass(frozen=True, slots=True)
class ToolSpec:
    """Tool declaration with workflow->chain targets."""

    tool_name: str
    factory: Callable[[], BaseTool]
    enabled_predicate: Callable[[object], bool]
    workflow_chain_targets: Mapping[ToolWorkflow, Sequence[str]]
    prompt_keys: Sequence[ToolPromptKey] = ()


def _kb_tools_enabled(config: object) -> bool:
    """Enable the KB tool when the KB feature is on (gated by KB_ENABLED)."""
    enabled = is_kb_feature_enabled(config)
    if enabled:
        logger.info("kb_tools_enabled", provider_mode=getattr(config, "KB_PROVIDER_MODE", None))
    else:
        logger.info("kb_tools_disabled")
    return enabled


def _create_example_kb_tool() -> BaseTool:
    return create_example_kb_tool()


TOOL_REGISTRY: tuple[ToolSpec, ...] = (
    ToolSpec(
        tool_name="query_example_knowledgebase",
        factory=_create_example_kb_tool,
        enabled_predicate=_kb_tools_enabled,
        workflow_chain_targets={
            "example": ("example",),
        },
        prompt_keys=(
            ToolPromptKey("example", "query_example_knowledgebase"),
        ),
    ),
)
