"""Prompt composition for dashboard insights workflow."""

from __future__ import annotations

from collections.abc import Sequence
from types import MappingProxyType

from app.agents.prompts.dashboard_insights_prompt import (
    DASHBOARD_INSIGHTS_SYSTEM_PROMPT,
)
from app.agents.tools.tool_assignment import build_prompt_bindings
from app.agents.tools.tool_prompts import ToolPromptKey

DASHBOARD_INSIGHTS_BASE_PROMPTS: MappingProxyType[str, str] = MappingProxyType(
    {
        "dashboard_insights": DASHBOARD_INSIGHTS_SYSTEM_PROMPT,
    }
)


def build_dashboard_insights_prompt(
    phase: str,
    tool_names: Sequence[str] | None = None,
    prompt_bindings: dict[ToolPromptKey, str] | None = None,
) -> str:
    """Build one dashboard-insights prompt from the base prompt and tools."""
    base_prompt = DASHBOARD_INSIGHTS_BASE_PROMPTS.get(phase)
    if base_prompt is None:
        raise KeyError(f"Unknown dashboard-insights chain '{phase}'.")

    parts = [base_prompt]
    resolved_bindings = prompt_bindings
    if resolved_bindings is None:
        resolved_bindings = build_prompt_bindings(tool_names or [])
    for tool_name in tool_names or []:
        snippet = resolved_bindings.get(ToolPromptKey(phase, tool_name))
        if snippet:
            parts.append(snippet)
    return "\n".join(parts)


def build_dashboard_insights_prompts(tool_names: Sequence[str]) -> dict[str, str]:
    """Build composed prompts for every dashboard-insights chain."""
    prompt_bindings = build_prompt_bindings(tool_names)
    return {
        phase: build_dashboard_insights_prompt(phase, tool_names, prompt_bindings)
        for phase in DASHBOARD_INSIGHTS_BASE_PROMPTS
    }
