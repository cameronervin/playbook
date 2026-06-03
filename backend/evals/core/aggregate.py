"""Aggregate per-item judge scores into a RunResult and check thresholds.

Scores are aggregated in-memory from what the judges returned this run (avoids
Langfuse read-after-write lag). Numeric scores are averaged per criterion;
non-numeric scores (e.g. a "skipped"/"error" Ragas metric) are ignored when
averaging but still surface in Langfuse. Each criterion is gated against the
spec's per-criterion threshold floor.
"""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Iterable
from statistics import mean

from evals.core.types import PerItemResult, RunResult, Score


def summarize(
    *,
    agent: str,
    run_name: str,
    scores: Iterable[Score],
    thresholds: dict[str, float],
    errors: list[str] | None = None,
    per_item: list[PerItemResult] | None = None,
) -> RunResult:
    """Average numeric scores per criterion and gate against thresholds.

    ``errors`` carries isolated per-item/per-rubric judging failures (the run still
    completed); they are surfaced in the result but do not by themselves flip
    ``passed`` — only threshold breaches do. ``per_item`` carries the individual
    item scores + reasoning that back the means; it is passed through untouched.
    """
    buckets: dict[str, list[float]] = defaultdict(list)
    for s in scores:
        if isinstance(s.value, (int, float)) and not isinstance(s.value, bool):
            buckets[s.name].append(float(s.value))

    mean_scores = {name: mean(vals) for name, vals in buckets.items() if vals}

    failures: list[str] = []
    for name, floor in thresholds.items():
        got = mean_scores.get(name)
        if got is None:
            failures.append(f"{name}: no numeric scores recorded")
        elif got < floor:
            failures.append(f"{name}: {got:.3f} < threshold {floor}")

    return RunResult(
        agent=agent,
        run_name=run_name,
        mean_scores=mean_scores,
        passed=len(failures) == 0,
        failures=failures,
        errors=list(errors or []),
        per_item=list(per_item or []),
    )
