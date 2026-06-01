"""Context policies defining what each agent chain receives.

Pattern: each chain has a ``PhaseContextPolicy`` listing the state fields to
inject and the serialization *tier* for each. The middleware reads the policy
rather than hardcoding context-assembly logic per chain, so adding context to a
chain is a data change (edit the policy) not a code change.

Serialization tiers:
    compact -> minimal, high-level (cheapest)
    full    -> complete data as readable text
    json    -> raw model_dump() (used for edit scenarios)
"""

from dataclasses import dataclass
from typing import Literal


@dataclass(frozen=True)
class ContextField:
    """A single context field to include for a chain.

    Attributes:
        name: The state key name (e.g. 'loaded_context', 'result').
        serialization: One of 'compact', 'full', or 'json'.
        required: Whether the field must be present (informational).
        description: Why this field is included.
        edit_field: True when the field is the chain's own prior output (edit mode).
    """

    name: str
    serialization: Literal["compact", "full", "json"]
    required: bool = True
    description: str = ""
    edit_field: bool = False


@dataclass(frozen=True)
class PhaseContextPolicy:
    """Context policy for a single chain."""

    phase: str
    fields: tuple[ContextField, ...]
    description: str = ""


EXAMPLE_POLICY = PhaseContextPolicy(
    phase="example",
    description="Generic chain - receives loaded context and prior result (edit mode)",
    fields=(
        ContextField(
            name="loaded_context",
            serialization="json",
            required=False,
            description="Context hydrated from persistence by load_state",
        ),
        ContextField(
            name="result",
            serialization="json",
            required=False,
            description="Existing result if re-running / editing",
            edit_field=True,
        ),
    ),
)


# All policies indexed by chain name.
CONTEXT_POLICIES = {
    "example": EXAMPLE_POLICY,
}


def get_policy(phase: str) -> PhaseContextPolicy:
    """Return the context policy for a chain.

    Raises:
        KeyError: If the chain has no registered policy.
    """
    return CONTEXT_POLICIES[phase]
