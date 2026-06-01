"""The example chain - a single LLM-call unit.

Pattern: a chain is the smallest composable unit - one ``create_agent`` call
bound to a system prompt, a structured ``response_format``, the graph state
schema, optional tools, and the context-injection middleware. Chains contain no
graph wiring or persistence; nodes orchestrate them.

To add a chain: copy this file, swap the prompt/response_format, register a
context policy + serializers, and add it to the chains builder.
"""

from typing import Any

from langchain.agents import create_agent
from langchain_core.language_models import BaseChatModel
from langchain_core.tools import BaseTool

from app.agents.context.middleware.example_middleware import create_context_injector
from app.agents.prompts.example_prompt import DEFAULT_EXAMPLE_PROMPT
from app.agents.states.example_state import ExampleResult, ExampleState


def create_example_chain(
    chat_model: BaseChatModel,
    tools: list[BaseTool] | None = None,
    prompt: str = DEFAULT_EXAMPLE_PROMPT,
) -> Any:
    """Create the example chain producing a structured ``ExampleResult``.

    Context injection is handled by the policy-driven middleware factory.
    ``state_schema`` is required so the middleware can read custom state fields.
    """
    return create_agent(
        model=chat_model,
        tools=tools,
        system_prompt=prompt,
        response_format=ExampleResult,
        state_schema=ExampleState,
        middleware=[create_context_injector("example")],
    )
