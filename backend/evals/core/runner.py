"""Orchestration — judge-agnostic and agent-agnostic.

For one spec:
  Phase 0  sync the on-disk YAML dataset into Langfuse (idempotent).
  Phase 1  let Langfuse run the dataset as an experiment with bounded
           concurrency. Each task invokes the agent, judges the GraphRun, and
           caches scores locally while Langfuse attaches traces/evaluations.
  Phase 2  aggregate the cached scores in-memory and check thresholds.

``get_client()`` is accessed lazily. The runner never branches on judge or agent
kind — that lives in ``specs/`` and ``core/judges/``.
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import subprocess
from dataclasses import dataclass, field
from datetime import UTC, datetime
from threading import RLock
from typing import Any

import structlog

from evals.core import aggregate
from evals.core.results import write_run_result
from evals.core.rubric import load_rubric
from evals.core.sync import sync_dataset_to_langfuse
from evals.core.types import EvalSpec, GraphRun, PerItemResult, RunResult, Score

logger = structlog.get_logger(__name__)


DEFAULT_MAX_CONCURRENCY = 5


@dataclass
class _ExperimentState:
    """Mutable per-run state shared by Langfuse task/evaluator callbacks."""

    scores_by_input: dict[str, list[Score]] = field(default_factory=dict)
    all_scores: list[Score] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    per_item: list[PerItemResult] = field(default_factory=list)
    lock: Any = field(default_factory=RLock)


def _item_id(item: Any) -> str:
    return str(getattr(item, "id", "?"))


def _item_input(item: Any) -> Any:
    if isinstance(item, dict):
        return item.get("input")
    return getattr(item, "input", None)


def _expected_output(item: Any) -> Any:
    if isinstance(item, dict):
        return item.get("expected_output")
    return getattr(item, "expected_output", None)


def _input_cache_key(input_obj: Any) -> str:
    raw = json.dumps(input_obj, sort_keys=True, default=str)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def _git_commit_sha() -> str | None:
    """Return the current commit SHA when this checkout is a git worktree."""
    try:
        completed = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            check=True,
            capture_output=True,
            text=True,
            timeout=2,
        )
    except Exception:  # noqa: BLE001 - metadata is best-effort only.
        return None
    sha = completed.stdout.strip()
    return sha or None


def _run_metadata(spec: EvalSpec, *, max_concurrency: int) -> dict[str, object]:
    """Build sanitized metadata persisted with local eval results."""
    metadata: dict[str, object] = {
        "dataset": spec.name,
        "dataset_path": spec.dataset_path,
        "thresholds": spec.thresholds,
        "max_concurrency": max_concurrency,
        "commit_sha": _git_commit_sha(),
        "created_at": datetime.now(UTC).isoformat(timespec="seconds"),
    }
    try:
        from app.core.config import get_settings  # noqa: PLC0415

        settings = get_settings()
        metadata.update(
            {
                "environment": settings.ENVIRONMENT,
                "llm_provider_mode": settings.LLM_PROVIDER_MODE,
                "llm_chat_model": settings.LLM_CHAT_MODEL,
                "eval_judge_model": settings.EVAL_JUDGE_MODEL
                or settings.LLM_CHAT_MODEL,
                "eval_embeddings_model": settings.EVAL_EMBEDDINGS_MODEL,
                "kb_provider_mode": settings.KB_PROVIDER_MODE,
            }
        )
    except Exception:  # noqa: BLE001 - app settings are helpful, not required.
        pass
    return metadata


def _langfuse_evaluations(scores: list[Score]) -> list[Any]:
    """Translate internal Scores into Langfuse Experiment Runner evaluations."""
    from langfuse import Evaluation  # noqa: PLC0415

    return [
        Evaluation(
            name=score.name,
            value=score.value,
            data_type=score.data_type,
            comment=score.comment,
        )
        for score in scores
    ]


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
            logger.exception(
                "eval_judge_failed", agent=spec.name, rubric=rubric.name, error=str(exc)
            )
            errors.append(f"rubric '{rubric.name}': {exc}")
    return scores, errors


async def run_spec(
    spec: EvalSpec,
    run_name: str | None = None,
    *,
    max_concurrency: int = DEFAULT_MAX_CONCURRENCY,
) -> RunResult:
    from langfuse import get_client  # noqa: PLC0415

    if max_concurrency < 1:
        raise ValueError("max_concurrency must be >= 1")

    langfuse = get_client()
    run_name = run_name or f"{spec.name}-{datetime.now(UTC).isoformat(timespec='seconds')}"

    # Phase 0: disk YAML is source of truth -> mirror into Langfuse (idempotent).
    sync_dataset_to_langfuse(spec.dataset_path, spec.name)
    dataset = langfuse.get_dataset(spec.name)

    state = _ExperimentState()

    async def _task(*, item: Any, **kwargs: Any) -> Any:
        """Run and score one item. Langfuse handles trace/evaluation attachment."""
        item_id = _item_id(item)
        try:
            graph_run = await spec.adapter(item=item)
        except Exception as exc:  # noqa: BLE001 — isolate one item's agent failure
            logger.exception("eval_agent_failed", agent=spec.name, item_id=item_id, error=str(exc))
            with state.lock:
                state.errors.append(f"agent run on item {item_id}: {exc}")
            raise

        trace_id = langfuse.get_current_trace_id()
        graph_run.trace_id = trace_id
        expected_output = _expected_output(item)
        scores, item_errors = await score_run(spec, graph_run, expected_output)

        with state.lock:
            state.errors.extend(item_errors)
            state.all_scores.extend(scores)
            state.per_item.append(_per_item_result(item_id, trace_id, scores))
            state.scores_by_input[_input_cache_key(_item_input(item))] = scores

        return graph_run.output

    def _evaluator(*, input: Any, output: Any, expected_output: Any = None, **kwargs: Any) -> list[Any]:
        """Return cached task scores in the shape Langfuse experiments ingest."""
        with state.lock:
            scores = list(state.scores_by_input.get(_input_cache_key(input), []))
        return _langfuse_evaluations(scores)

    def _run_experiment() -> Any:
        return langfuse.run_experiment(
            name=run_name,
            dataset=dataset,
            task=_task,
            evaluators=[_evaluator],
            max_concurrency=max_concurrency,
            description=(
                f"Playbook eval for {spec.name}; "
                f"judge={type(spec.judge).__name__}; concurrency={max_concurrency}"
            ),
        )

    # The SDK runner is synchronous while supporting async tasks. Run it in a
    # worker thread so our async CLI entrypoint never nests event loops.
    await asyncio.to_thread(_run_experiment)
    langfuse.flush()

    # Phase 2: aggregate in-memory + threshold check, then persist for review.
    result = aggregate.summarize(
        agent=spec.name,
        run_name=run_name,
        scores=state.all_scores,
        thresholds=spec.thresholds,
        errors=state.errors,
        per_item=state.per_item,
        metadata=_run_metadata(spec, max_concurrency=max_concurrency),
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
