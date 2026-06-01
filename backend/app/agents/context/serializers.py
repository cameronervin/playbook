"""Context serializers for agent middleware.

Pattern: a serializer turns a state value into a token-efficient string for LLM
injection. Serializers are registered by ``(field_name, tier)`` so the
policy-driven middleware can look one up dynamically. The ``json`` tier falls
back to a generic ``serialize_to_json`` for any Pydantic model.

Add a serializer when a new state field needs a compact/full representation;
register it in ``SERIALIZER_REGISTRY``.
"""

from __future__ import annotations

import json
from collections.abc import Callable
from typing import Any

from app.agents.states.example_state import ExampleResult


def serialize_example_result_compact(result: ExampleResult) -> str:
    """Compact view of an ExampleResult: title + truncated body."""
    body = result.body or ""
    if len(body) > 200:
        body = body[:197] + "..."
    return f"**{result.title}**\n\n{body}"


def serialize_example_result_full(result: ExampleResult) -> str:
    """Full view of an ExampleResult: title + complete body."""
    return f"**{result.title}**\n\n{result.body}"


def serialize_to_json(obj: Any, indent: int = 2) -> str:
    """Serialize a Pydantic model (or any JSON-able object) to a JSON string."""
    if hasattr(obj, "model_dump"):
        return json.dumps(obj.model_dump(), indent=indent, default=str)
    return json.dumps(obj, indent=indent, default=str)


def _serialize_loaded_context(obj: Any) -> str:
    """Serialize the raw loaded_context dict, skipping empties."""
    if not obj:
        return ""
    return json.dumps(obj, indent=2, default=str)


# Registry mapping (field_name, tier) -> serializer function.
SERIALIZER_REGISTRY: dict[tuple[str, str], Callable[[Any], str]] = {
    ("result", "compact"): serialize_example_result_compact,
    ("result", "full"): serialize_example_result_full,
    ("loaded_context", "json"): _serialize_loaded_context,
    ("loaded_context", "compact"): _serialize_loaded_context,
    ("loaded_context", "full"): _serialize_loaded_context,
}


def get_serializer(field_name: str, tier: str) -> Callable[[Any], str]:
    """Return the serializer for a (field_name, tier) pair.

    The ``json`` tier uses a field-specific serializer when registered,
    otherwise the generic ``serialize_to_json``.

    Raises:
        KeyError: If a compact/full serializer is requested but not registered.
    """
    if tier == "json":
        if (field_name, "json") in SERIALIZER_REGISTRY:
            return SERIALIZER_REGISTRY[(field_name, "json")]
        return serialize_to_json
    return SERIALIZER_REGISTRY[(field_name, tier)]
