"""Prompt composition for the athlete chat workflow."""

from __future__ import annotations

from collections.abc import Sequence
from types import MappingProxyType

from app.agents.prompts.athlete_chat_prompt import ATHLETE_CHAT_SYSTEM_PROMPT
from app.agents.tools.tool_assignment import build_prompt_bindings
from app.agents.tools.tool_prompts import ToolPromptKey

ATHLETE_CHAT_BASE_PROMPTS: MappingProxyType[str, str] = MappingProxyType(
    {
        "athlete_chat": ATHLETE_CHAT_SYSTEM_PROMPT,
    }
)


def build_athlete_chat_prompt(
    phase: str,
    tool_names: Sequence[str] | None = None,
    prompt_bindings: dict[ToolPromptKey, str] | None = None,
) -> str:
    """Build one athlete-chat prompt from the base prompt and active tools."""
    base_prompt = ATHLETE_CHAT_BASE_PROMPTS.get(phase)
    if base_prompt is None:
        raise KeyError(f"Unknown athlete-chat chain '{phase}'.")

    parts = [base_prompt]
    resolved_bindings = prompt_bindings
    if resolved_bindings is None:
        resolved_bindings = build_prompt_bindings(tool_names or [])
    for tool_name in tool_names or []:
        snippet = resolved_bindings.get(ToolPromptKey(phase, tool_name))
        if snippet:
            parts.append(snippet)
    return "\n".join(parts)


def build_athlete_chat_prompts(tool_names: Sequence[str]) -> dict[str, str]:
    """Build composed prompts for every athlete-chat chain."""
    prompt_bindings = build_prompt_bindings(tool_names)
    return {
        phase: build_athlete_chat_prompt(phase, tool_names, prompt_bindings)
        for phase in ATHLETE_CHAT_BASE_PROMPTS
    }
