"""Policy-driven middleware factory for context injection.

Pattern: ``create_context_injector(phase)`` reads the chain's
``PhaseContextPolicy``, serializes each declared state field with its tier,
budgets the assembled context, scopes the message history to the current turn,
and appends the context as a final ``HumanMessage`` before the model call.

This is the single, generic injector — one factory generates the middleware for
every chain from its policy, instead of one hand-written middleware per chain.
Wire it into a chain via ``middleware=[create_context_injector("example")]``.
"""

from collections.abc import Callable

import structlog
from langchain.agents.middleware import ModelRequest, wrap_model_call
from langchain.agents.middleware.types import ModelResponse
from langchain.messages import HumanMessage
from langchain_core.messages import AIMessage, SystemMessage, ToolMessage

from app.agents.context.policies import PhaseContextPolicy, get_policy
from app.agents.context.serializers import get_serializer
from app.agents.context.token_budget import enforce_context_token_budget
from app.agents.guardrails import (
    assert_message_loop_bounded,
    scope_messages_to_current_turn,
)

logger = structlog.get_logger(__name__)

# Human-readable labels for context sections in the injected message.
FIELD_LABELS: dict[str, str] = {
    "loaded_context": "Loaded Context",
    "result": "Result",
}


def _serialize_policy_fields(
    policy: PhaseContextPolicy,
    state: dict,
    phase: str,
    example_id: str,
) -> tuple[list[str], list[str]]:
    """Serialize each policy field; return (parts, skipped_fields)."""
    parts: list[str] = []
    skipped_fields: list[str] = []

    for field in policy.fields:
        value = state.get(field.name)
        if value is None:
            skipped_fields.append(f"{field.name}(None)")
            continue

        serializer = get_serializer(field.name, field.serialization)
        try:
            serialized = serializer(value)
        except Exception as exc:
            logger.exception(
                "context_serialization_failed",
                phase=phase,
                field=field.name,
                example_id=example_id,
                error=str(exc),
            )
            skipped_fields.append(f"{field.name}(error)")
            continue

        if not serialized or not serialized.strip():
            skipped_fields.append(f"{field.name}(empty)")
            continue

        label = FIELD_LABELS.get(field.name, field.name.replace("_", " ").title())
        if field.edit_field:
            label = f"{label} to Edit"
        parts.append(f"## {label}\n{serialized}")

    return parts, skipped_fields


def _build_context_string(parts: list[str]) -> str:
    """Join context parts; fall back to a placeholder when empty."""
    context = "\n\n---\n\n".join(parts) if parts else ""
    if not context.strip():
        return "No context available."
    return context


def _filter_blank_messages(messages: list, phase: str, example_id: str) -> tuple[list, int]:
    """Drop blank-content messages while preserving tool-call pairs and SystemMessages."""
    valid_messages: list = []
    filtered_count = 0

    for msg in messages:
        if isinstance(msg, AIMessage) and getattr(msg, "tool_calls", None):
            valid_messages.append(msg)
            continue
        if isinstance(msg, (ToolMessage, SystemMessage)):
            valid_messages.append(msg)
            continue

        content = msg.content if hasattr(msg, "content") else str(msg)
        if content and str(content).strip():
            valid_messages.append(msg)
        else:
            filtered_count += 1

    return valid_messages, filtered_count


def create_context_injector(phase: str) -> Callable:
    """Factory that builds context-injection middleware from a chain's policy.

    Args:
        phase: The chain name (must have a registered context policy).

    Returns:
        A ``@wrap_model_call`` middleware coroutine.

    Raises:
        KeyError: If ``phase`` has no policy in ``CONTEXT_POLICIES``.
    """
    policy = get_policy(phase)

    @wrap_model_call
    async def inject_context(
        request: ModelRequest,
        handler: Callable[[ModelRequest], ModelResponse],
    ) -> ModelResponse:
        """Inject policy-defined context from state into the model request."""
        state = request.state
        example_id = str(state.get("example_id", "unknown"))

        parts, skipped_fields = _serialize_policy_fields(policy, state, phase, example_id)
        logger.debug(
            "context_fields_processed",
            phase=phase,
            example_id=example_id,
            included_count=len(parts),
            skipped=skipped_fields or None,
        )

        context = _build_context_string(parts)
        context = enforce_context_token_budget(context, phase=phase, example_id=example_id)

        valid_messages, filtered_count = _filter_blank_messages(request.messages, phase, example_id)
        scoped_messages = scope_messages_to_current_turn(valid_messages)
        assert_message_loop_bounded(scoped_messages, phase=phase, example_id=example_id)

        if filtered_count:
            logger.info(
                "filtered_blank_messages",
                phase=phase,
                example_id=example_id,
                filtered_count=filtered_count,
            )

        messages = [*scoped_messages, HumanMessage(content=context)]
        return await handler(request.override(messages=messages))

    return inject_context
