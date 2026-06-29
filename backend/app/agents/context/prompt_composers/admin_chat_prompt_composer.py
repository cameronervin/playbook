"""Prompt composition for admin chat workflow."""

from __future__ import annotations

from collections.abc import Sequence
from types import MappingProxyType

from app.agents.prompts.admin_chat_prompt import ADMIN_CHAT_SYSTEM_PROMPT
from app.agents.tools.tool_assignment import build_prompt_bindings
from app.agents.tools.tool_prompts import ToolPromptKey

ADMIN_CHAT_BASE_PROMPTS: MappingProxyType[str, str] = MappingProxyType(
    {
        "admin_chat": ADMIN_CHAT_SYSTEM_PROMPT,
    }
)


def build_admin_chat_prompt(
    phase: str,
    tool_names: Sequence[str] | None = None,
    prompt_bindings: dict[ToolPromptKey, str] | None = None,
) -> str:
    """Build one admin-chat prompt from the base prompt and tools."""
    base_prompt = ADMIN_CHAT_BASE_PROMPTS.get(phase)
    if base_prompt is None:
        raise KeyError(f"Unknown admin-chat chain '{phase}'.")

    parts = [base_prompt]
    resolved_bindings = prompt_bindings
    if resolved_bindings is None:
        resolved_bindings = build_prompt_bindings(tool_names or [])
    for tool_name in tool_names or []:
        snippet = resolved_bindings.get(ToolPromptKey(phase, tool_name))
        if snippet:
            parts.append(snippet)
    return "\n".join(parts)


def build_admin_chat_prompts(tool_names: Sequence[str]) -> dict[str, str]:
    """Build composed prompts for every admin-chat chain."""
    prompt_bindings = build_prompt_bindings(tool_names)
    return {
        phase: build_admin_chat_prompt(phase, tool_names, prompt_bindings)
        for phase in ADMIN_CHAT_BASE_PROMPTS
    }
