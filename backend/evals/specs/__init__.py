"""Per-agent eval specs + the REGISTRY the CLI runs against.

The scaffold ships a single ``example`` spec. It uses an LLM-as-judge for its
content rubric and, because it is a KB-using chain, additionally runs Ragas
(retrieval + generation) via a CompositeJudge. Add more specs by writing a new
``specs/<name>.py`` exporting a ``SPEC`` and registering it below.
"""

from __future__ import annotations

from evals.core.types import EvalSpec
from evals.specs.dashboard_insights import SPEC as dashboard_insights_spec
from evals.specs.example import SPEC as example_spec

REGISTRY: dict[str, EvalSpec] = {
    example_spec.name: example_spec,
    dashboard_insights_spec.name: dashboard_insights_spec,
}

__all__ = ["REGISTRY"]
