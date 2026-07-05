"""Context policies defining what each agent chain receives.

Pattern: workflow middleware can use ``PhaseContextPolicy`` rows to list the
state fields to inject and the serialization *tier* for each. Athlete chat uses
custom middleware today, so this registry is intentionally empty until another
workflow needs declarative context injection.

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
        name: The state key name.
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


# All policies indexed by chain name.
CONTEXT_POLICIES: dict[str, PhaseContextPolicy] = {}


def get_policy(phase: str) -> PhaseContextPolicy:
    """Return the context policy for a chain.

    Raises:
        KeyError: If the chain has no registered policy.
    """
    return CONTEXT_POLICIES[phase]
