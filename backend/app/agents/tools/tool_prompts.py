"""Tool-specific prompt snippets, keyed by (chain, tool_name).

Pattern: when a tool is active for a given chain, its snippet is appended to
that chain's base system prompt by the prompt composer. This keeps tool usage
guidance co-located with the tool and out of the base prompts.
"""

from typing import NamedTuple


class ToolPromptKey(NamedTuple):
    """Identifies a prompt snippet by the chain it targets and the tool it documents."""

    chain: str
    tool_name: str


EXAMPLE_KB_PROMPT = """
<tools>
- **query_example_knowledgebase**:
You have access to a knowledge base retrieval tool.

Query it for any supporting context that would improve your result. Prefer
focused, specific queries over broad ones — narrower queries yield
higher-relevance results. Treat the user's request as the primary source of
truth and use retrieved context only to enhance your output.
</tools>
"""


TOOL_PROMPT_REGISTRY: dict[ToolPromptKey, str] = {
    ToolPromptKey("example", "query_example_knowledgebase"): EXAMPLE_KB_PROMPT,
}
