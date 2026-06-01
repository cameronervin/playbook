"""Graph state schema for the generic ``example`` workflow.

Pattern: a LangGraph state is a ``TypedDict`` with ``total=False`` so nodes can
return partial updates. The ``messages`` channel uses the ``add_messages``
reducer so message lists are merged (appended) across node returns rather than
overwritten — this is the canonical LangGraph conversation pattern.

``ExampleResult`` is the structured artifact this workflow produces. Replace it
with your real domain schema(s); keep the state-as-TypedDict + reducer shape.
"""

from __future__ import annotations

from typing import Annotated, TypedDict
from uuid import UUID

from langchain_core.messages import BaseMessage
from langgraph.graph.message import add_messages
from pydantic import BaseModel, Field


class ExampleResult(BaseModel):
    """Structured output produced by the example chain.

    A deliberately small, domain-neutral schema. The chain uses this as its
    ``response_format`` so the LLM is forced to return structured data.
    """

    title: str = Field(..., description="Short title summarizing the result")
    body: str = Field(..., description="Main generated text content")


class ExampleState(TypedDict, total=False):
    """State schema for the example LangGraph.

    Using ``TypedDict`` for performance (recommended by LangGraph docs).
    All fields are optional (``total=False``) to support partial updates.
    """

    # Set at graph invocation
    messages: Annotated[list[BaseMessage], add_messages]
    example_id: UUID
    decision: str

    # Loaded from persistence by the load_state node (optional until hydrated)
    loaded_context: dict | None

    # Produced by the chain node (optional until generated)
    result: ExampleResult | None
