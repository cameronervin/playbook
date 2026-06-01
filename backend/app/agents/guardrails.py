"""Agent execution guardrails - message scoping and loop detection.

Pattern: these helpers are called by the context middleware before every model
call. ``scope_messages_to_current_turn`` keeps the LLM focused on the active
turn (system prompts + latest human turn + trailing tool pairs), and
``assert_message_loop_bounded`` fails fast if message fan-out suggests an
unbounded tool/repair loop.
"""

from __future__ import annotations

import structlog
from langchain_core.messages import (
    AIMessage,
    BaseMessage,
    HumanMessage,
    SystemMessage,
    ToolMessage,
)

from app.core.config import settings
from app.core.exceptions import ValidationError

logger = structlog.get_logger(__name__)

# Bounded repair retries for structured-output validation (see chains node).
RESULT_MAX_REPAIR_RETRIES = 2

# Fallback cap when the app does not configure AGENT_MAX_MESSAGES_PER_LLM_CALL.
_DEFAULT_MAX_MESSAGES = 60


def _max_messages_per_call() -> int:
    return getattr(settings, "AGENT_MAX_MESSAGES_PER_LLM_CALL", _DEFAULT_MAX_MESSAGES)


def scope_messages_to_current_turn(messages: list[BaseMessage]) -> list[BaseMessage]:
    """Pass system prompts plus the active turn only (latest human + tool tail).

    Excludes older checkpoint conversation history from LLM calls while
    preserving trailing tool_use/tool_result pairs.
    """
    system_messages = [msg for msg in messages if isinstance(msg, SystemMessage)]

    last_human_idx: int | None = None
    for idx, msg in enumerate(messages):
        if isinstance(msg, HumanMessage):
            last_human_idx = idx

    if last_human_idx is None:
        return system_messages

    # Walk back through tool-call pairs so a repair HumanMessage after tool use
    # does not drop the tool results from the scoped context.
    turn_start = last_human_idx
    idx = last_human_idx - 1
    walked_tool_chain = False
    while idx >= 0:
        msg = messages[idx]
        if isinstance(msg, ToolMessage):
            turn_start = idx
            walked_tool_chain = True
            idx -= 1
            continue
        if isinstance(msg, AIMessage) and getattr(msg, "tool_calls", None):
            turn_start = idx
            walked_tool_chain = True
            idx -= 1
            continue
        if isinstance(msg, HumanMessage) and walked_tool_chain:
            turn_start = idx
        break

    turn_messages = [
        msg for msg in messages[turn_start:] if not isinstance(msg, SystemMessage)
    ]
    return system_messages + turn_messages


def assert_message_loop_bounded(
    messages: list[BaseMessage],
    *,
    phase: str,
    example_id: str,
) -> None:
    """Fail fast when message fan-out suggests an unbounded loop."""
    max_messages = _max_messages_per_call()
    if len(messages) <= max_messages:
        return

    logger.error(
        "agent_message_loop_guard_triggered",
        phase=phase,
        example_id=example_id,
        message_count=len(messages),
        max_allowed=max_messages,
    )
    raise ValidationError(
        message=(
            f"Agent message loop guard triggered for chain '{phase}' "
            f"({len(messages)} messages > {max_messages})"
        ),
        details={
            "phase": phase,
            "example_id": example_id,
            "message_count": len(messages),
            "max_messages": max_messages,
        },
    )


def count_tool_messages(messages: list[BaseMessage]) -> int:
    """Count ToolMessage instances - useful for retry/loop telemetry."""
    return sum(1 for msg in messages if isinstance(msg, ToolMessage))


def count_ai_tool_calls(messages: list[BaseMessage]) -> int:
    """Count tool calls initiated across all AIMessages."""
    total = 0
    for msg in messages:
        if isinstance(msg, AIMessage) and getattr(msg, "tool_calls", None):
            total += len(msg.tool_calls)
    return total
