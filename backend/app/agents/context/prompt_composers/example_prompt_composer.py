"""Prompt composition for the example workflow.

Pattern: the final system prompt for a chain is its base prompt plus any prompt
snippets contributed by the tools active for that chain. Keeping composition
here (rather than in the builder) lets runtime paths reuse it and keeps the
base prompt strings tool-agnostic.
"""

from collections.abc import Sequence
from types import MappingProxyType

from app.agents.prompts.example_prompt import DEFAULT_EXAMPLE_PROMPT
from app.agents.tools.tool_assignment import build_prompt_bindings
from app.agents.tools.tool_prompts import ToolPromptKey

EXAMPLE_BASE_PROMPTS: MappingProxyType[str, str] = MappingProxyType({
    "example": DEFAULT_EXAMPLE_PROMPT,
})


def build_example_prompt(
    phase: str,
    tool_names: Sequence[str] | None = None,
    prompt_bindings: dict[ToolPromptKey, str] | None = None,
) -> str:
    """Build one example-workflow chain prompt from active tool names."""
    base_prompt = EXAMPLE_BASE_PROMPTS.get(phase)
    if base_prompt is None:
        raise KeyError(f"Unknown example-workflow chain '{phase}'.")

    parts = [base_prompt]
    resolved_bindings = prompt_bindings
    if resolved_bindings is None:
        resolved_bindings = build_prompt_bindings(tool_names or [])
    for tool_name in tool_names or []:
        snippet = resolved_bindings.get(ToolPromptKey(phase, tool_name))
        if snippet:
            parts.append(snippet)
    return "\n".join(parts)


def build_example_prompts(tool_names: Sequence[str]) -> dict[str, str]:
    """Build composed prompts for every example-workflow chain."""
    prompt_bindings = build_prompt_bindings(tool_names)
    return {
        phase: build_example_prompt(phase, tool_names, prompt_bindings)
        for phase in EXAMPLE_BASE_PROMPTS
    }
