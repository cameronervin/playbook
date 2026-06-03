"""Shared vocabulary for the eval harness.

Adapters produce ``GraphRun``s; judges consume them and emit ``Score``s; specs
are declared as ``EvalSpec``s; the runner returns a ``RunResult``.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, Literal

if TYPE_CHECKING:
    # Type-only import to avoid a runtime circular import with judges/base.py.
    from evals.core.judges.base import Judge


@dataclass
class GraphRun:
    """Snapshot of one agent invocation. Adapters produce these; judges consume them."""

    input: Any  # the dataset item's input, untouched
    output: Any  # final agent answer (serialised structured output or text)
    events: list[dict] = field(default_factory=list)  # trajectory: node visits, tool calls
    trace_id: str | None = None  # filled by the runner after fetch


@dataclass
class Score:
    """One judge score for one criterion/metric on one trace."""

    name: str
    value: float | str | bool
    data_type: Literal["NUMERIC", "CATEGORICAL", "BOOLEAN"] = "NUMERIC"
    comment: str | None = None


@dataclass
class EvalSpec:
    """Everything needed to evaluate one agent. Declarative, no side effects."""

    name: str  # also the Langfuse dataset name
    dataset_path: str  # YAML on disk
    adapter: Callable[..., GraphRun]  # how to run THIS chain (returns a GraphRun)
    rubrics: list[str]  # paths to rubric YAMLs
    judge: "Judge"  # polymorphic strategy object (LLM, Ragas, or Composite)
    thresholds: dict[str, float] = field(default_factory=dict)  # per-criterion CI gates


@dataclass
class PerItemResult:
    """One dataset item's judge scores, kept alongside the run aggregate.

    ``scores`` maps each criterion name to ``{"score": float, "reasoning": str}``
    (reasoning omitted when the judge gave none). This is the per-item detail that
    backs the aggregate means — e.g. which items dragged a criterion down, and the
    judge's stated reason for each — and is persisted to the results JSON/Markdown.
    """

    item_id: str
    trace_id: str | None
    scores: dict[str, dict[str, object]] = field(default_factory=dict)


@dataclass
class RunResult:
    """Aggregated outcome of one eval run."""

    agent: str
    run_name: str
    mean_scores: dict[str, float]
    passed: bool
    failures: list[str]
    # Per-item/per-rubric judging failures that were isolated (not raised), e.g. a
    # judge model rejecting an oversized prompt. The run still completes; these are
    # recorded so they surface in the summary instead of aborting the whole suite.
    errors: list[str] = field(default_factory=list)
    # Per-item scores + reasoning backing the aggregate means (one per dataset item).
    per_item: list[PerItemResult] = field(default_factory=list)

    def summary(self) -> str:
        status = "PASS" if self.passed else "FAIL"
        lines = [f"[{status}] {self.agent} ({self.run_name})"]
        for name, val in sorted(self.mean_scores.items()):
            lines.append(f"  {name}: {val:.3f}")
        for failure in self.failures:
            lines.append(f"  ! {failure}")
        for err in self.errors:
            lines.append(f"  ⚠ {err}")
        return "\n".join(lines)
