"""Declarative registry of chain-scoped agent tools.

Tools are declared once as frozen ``ToolSpec`` rows in ``TOOL_REGISTRY``.
Runtime assignment and prompt composition pick them up automatically, so graph
builders do not need to know profile details for individual tools.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from typing import Literal

import structlog
from langchain_core.tools import BaseTool

from app.agents.tools.knowledgebase import (
    ATHLETE_CONVERSATION_FILE_TOOL_PROFILE,
    ATHLETE_KB_TOOL_PROFILE,
    create_conversation_file_search_tool,
    create_knowledgebase_search_tool,
)
from app.agents.tools.tool_prompts import ToolPromptKey
from app.infrastructure.knowledgebase import (
    is_kb_feature_enabled,
)

logger = structlog.get_logger(__name__)

ToolWorkflow = Literal["athlete_chat"]

ATHLETE_CHAT_CHAIN_NAMES: tuple[str, ...] = ("athlete_chat",)

WORKFLOW_CHAIN_NAMES: dict[ToolWorkflow, tuple[str, ...]] = {
    "athlete_chat": ATHLETE_CHAT_CHAIN_NAMES,
}


@dataclass(slots=True)
class ToolBuildContext:
    """Context passed to registry factories when building tools."""

    settings: object


@dataclass(frozen=True, slots=True)
class ToolSpec:
    """Tool declaration with workflow->chain targets."""

    tool_name: str
    factory: Callable[[ToolBuildContext], BaseTool]
    enabled_predicate: Callable[[ToolBuildContext], bool]
    workflow_chain_targets: Mapping[ToolWorkflow, Sequence[str]]
    prompt_keys: Sequence[ToolPromptKey] = ()


def _kb_tools_enabled(context: ToolBuildContext) -> bool:
    """Enable KB tools when the KB feature is on."""
    enabled = is_kb_feature_enabled(context.settings)
    if enabled:
        logger.info(
            "kb_tools_enabled",
            provider_mode=getattr(context.settings, "KB_PROVIDER_MODE", None),
        )
    else:
        logger.info("kb_tools_disabled")
    return enabled


def _create_athlete_kb_tool(_context: ToolBuildContext) -> BaseTool:
    return create_knowledgebase_search_tool(ATHLETE_KB_TOOL_PROFILE)


def _create_athlete_conversation_file_tool(_context: ToolBuildContext) -> BaseTool:
    return create_conversation_file_search_tool(ATHLETE_CONVERSATION_FILE_TOOL_PROFILE)


TOOL_REGISTRY: tuple[ToolSpec, ...] = (
    ToolSpec(
        tool_name=ATHLETE_KB_TOOL_PROFILE.tool_name,
        factory=_create_athlete_kb_tool,
        enabled_predicate=_kb_tools_enabled,
        workflow_chain_targets={
            "athlete_chat": ("athlete_chat",),
        },
        prompt_keys=(ToolPromptKey("athlete_chat", ATHLETE_KB_TOOL_PROFILE.tool_name),),
    ),
    ToolSpec(
        tool_name=ATHLETE_CONVERSATION_FILE_TOOL_PROFILE.tool_name,
        factory=_create_athlete_conversation_file_tool,
        enabled_predicate=_kb_tools_enabled,
        workflow_chain_targets={
            "athlete_chat": ("athlete_chat",),
        },
        prompt_keys=(
            ToolPromptKey(
                "athlete_chat",
                ATHLETE_CONVERSATION_FILE_TOOL_PROFILE.tool_name,
            ),
        ),
    ),
)
