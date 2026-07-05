from __future__ import annotations

from typing import Any

import pytest
from langchain_core.language_models import BaseChatModel
from langchain_core.messages import AIMessage, HumanMessage
from langchain_core.outputs import ChatGeneration, ChatResult
from pydantic import ConfigDict

from app.agents.chains.athlete_chat_chain import create_athlete_chat_chain
from app.agents.chains.conversation_title_chain import (
    create_conversation_title_chain,
)
from app.agents.states.athlete_chat_state import (
    AthleteChatState,
    AthleteChatStructuredResponse,
)
from app.agents.states.conversation_title_state import (
    ConversationTitleStructuredResponse,
)


class StructuredToolCallModel(BaseChatModel):
    """Fake model that returns a valid structured-output tool call."""

    model_config = ConfigDict(arbitrary_types_allowed=True)

    tool_args: dict[str, Any]
    calls: int = 0
    tool_name: str = ""

    @property
    def _llm_type(self) -> str:
        return "structured-tool-call"

    def bind_tools(self, tools: list[Any], **_: Any) -> "StructuredToolCallModel":
        self.tool_name = str(tools[-1].name)
        return self

    def _generate(
        self,
        messages: list[Any],
        stop: list[str] | None = None,
        run_manager: Any | None = None,
        **_: Any,
    ) -> ChatResult:
        self.calls += 1
        message = AIMessage(
            content="",
            tool_calls=[
                {
                    "name": self.tool_name,
                    "args": self.tool_args,
                    "id": f"structured_call_{self.calls}",
                    "type": "tool_call",
                }
            ],
        )
        return ChatResult(generations=[ChatGeneration(message=message)])


@pytest.mark.asyncio
async def test_conversation_title_chain_preserves_structured_response() -> None:
    model = StructuredToolCallModel(
        tool_args={"title": "NIL Disclosure Basics"},
    )
    chain = create_conversation_title_chain(title_model=model)

    result = await chain.ainvoke(
        {"messages": [HumanMessage(content="Create a title.")]},
        config={"recursion_limit": 5},
    )

    assert result["structured_response"] == ConversationTitleStructuredResponse(
        title="NIL Disclosure Basics",
    )
    assert model.calls == 1


@pytest.mark.asyncio
async def test_athlete_chat_chain_preserves_structured_response(test_settings) -> None:
    model = StructuredToolCallModel(
        tool_args={"answer": "You should disclose the NIL deal."},
    )
    chain = create_athlete_chat_chain(
        chat_model=model,
        tools=[],
        settings=test_settings,
    )

    result = await chain.ainvoke(
        {
            "messages": [HumanMessage(content="Can I accept this NIL deal?")],
            "conversation_id": "conversation-1",
            "task_id": "task-1",
        },
        config={"recursion_limit": 5},
    )

    assert result["structured_response"] == AthleteChatStructuredResponse(
        answer="You should disclose the NIL deal.",
    )
    assert model.calls == 1


def test_athlete_chat_state_has_no_keyword_kb_requirement_flag() -> None:
    assert "requires_kb_support" not in AthleteChatState.__annotations__
