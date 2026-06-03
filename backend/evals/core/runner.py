"""Orchestration — judge-agnostic and agent-agnostic.

For one spec:
  Phase 0  sync the on-disk YAML dataset into Langfuse (idempotent).
  Phase 1  run the agent over every item inside ``item.run(run_name=...)`` so each
           trace is linked to the dataset run; keep the returned GraphRun in memory.
  Phase 2  judge each GraphRun across the spec's rubrics; push scores to its trace.
  Phase 3  aggregate the scores in-memory and check thresholds.

``get_client()`` is accessed lazily. The runner never branches on judge or agent
kind — that lives in ``specs/`` and ``core/judges/``.
"""

from __future__ import annotations

from datetime import datetime

import structlog

from evals.core import aggregate
from evals.core.results import write_run_result
from evals.core.rubric import load_rubric
from evals.core.sync import sync_dataset_to_langfuse
from evals.core.types import EvalSpec, GraphRun, PerItemResult, RunResult, Score

logger = structlog.get_logger(__name__)


def _per_item_result(item_id: str, trace_id: str | None, scores: list[Score]) -> PerItemResult:
    """Fold one item's judge Scores into a {criterion: {score, reasoning}} record."""
    by_criterion: dict[str, dict[str, object]] = {}
    for s in scores:
        entry: dict[str, object] = {"score": s.value}
        if s.comment is not None:
            entry["reasoning"] = s.comment
        by_criterion[s.name] = entry
    return PerItemResult(item_id=item_id, trace_id=trace_id, scores=by_criterion)


async def score_run(
    spec: EvalSpec, run: GraphRun, expected_output: object
) -> tuple[list[Score], list[str]]:
    """Judge one GraphRun across all of the spec's rubrics.

    Each rubric is judged independently: a failure on one rubric (e.g. the judge
    model rejecting an oversized prompt) is caught and recorded rather than raised,
    so the remaining rubrics and items still score. Returns ``(scores, errors)``.
    """
    scores: list[Score] = []
    errors: list[str] = []
    for rubric_path in spec.rubrics:
        rubric = load_rubric(rubric_path)
        try:
            scores += await spec.judge.score(
                run=run,
                rubric=rubric,
                expected_output=expected_output,
            )
        except Exception as exc:  # noqa: BLE001 — isolate one rubric's failure
            logger.error(
                "eval_judge_failed", agent=spec.name, rubric=rubric.name, error=str(exc)
            )
            errors.append(f"rubric '{rubric.name}': {exc}")
    return scores, errors


async def run_spec(spec: EvalSpec, run_name: str | None = None) -> RunResult:
    from langfuse import get_client

    langfuse = get_client()
    run_name = run_name or f"{spec.name}-{datetime.now().isoformat(timespec='seconds')}"

    # Phase 0: disk YAML is source of truth -> mirror into Langfuse (idempotent).
    sync_dataset_to_langfuse(spec.dataset_path, spec.name)
    dataset = langfuse.get_dataset(spec.name)

    # Phase 1: run the agent over every item, linking each trace to the dataset run.
    # A single item's agent crash is isolated so the rest of the run continues.
    runs: list[tuple[str, str, object, GraphRun]] = []  # (item_id, trace_id, expected, GraphRun)
    errors: list[str] = []
    run_metadata = {"agent": spec.name, "judge": type(spec.judge).__name__}
    for item in dataset.items:
        item_id = str(getattr(item, "id", "?"))
        try:
            with item.run(run_name=run_name, run_metadata=run_metadata):
                graph_run = await spec.adapter(item=item)
                # The dataset-run span is the active context here, so this resolves
                # to its trace id (LangfuseSpan exposes no .trace_id attribute).
                trace_id = langfuse.get_current_trace_id()
            runs.append((item_id, trace_id, item.expected_output, graph_run))
        except Exception as exc:  # noqa: BLE001 — isolate one item's agent failure
            logger.error("eval_agent_failed", agent=spec.name, item_id=item_id, error=str(exc))
            errors.append(f"agent run on item {item_id}: {exc}")
    langfuse.flush()

    # Phase 2: judge each GraphRun (held in memory), push scores back to its trace,
    # and keep the per-item scores + reasoning that back the aggregate means.
    all_scores: list[Score] = []
    per_item: list[PerItemResult] = []
    for item_id, trace_id, expected_output, graph_run in runs:
        graph_run.trace_id = trace_id
        scores, item_errors = await score_run(spec, graph_run, expected_output)
        errors.extend(item_errors)
        all_scores.extend(scores)
        per_item.append(_per_item_result(item_id, trace_id, scores))
        for s in scores:
            langfuse.create_score(
                trace_id=trace_id,
                name=s.name,
                value=s.value,
                data_type=s.data_type,
                comment=s.comment,
            )
    langfuse.flush()

    # Phase 3: aggregate in-memory + threshold check, then persist for review.
    result = aggregate.summarize(
        agent=spec.name,
        run_name=run_name,
        scores=all_scores,
        thresholds=spec.thresholds,
        errors=errors,
        per_item=per_item,
    )
    json_path, _ = write_run_result(result)
    logger.info(
        "eval_run_complete",
        agent=spec.name,
        run_name=run_name,
        passed=result.passed,
        errors=len(result.errors),
        results_file=str(json_path),
    )
    return result
