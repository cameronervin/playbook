"""Eval spec for dashboard insight structural quality.

This spec is intentionally deterministic: it validates seeded dashboard insight
outputs against source counts and expected labels without constructing an LLM
judge or requiring provider environment variables during unit tests.
"""

from __future__ import annotations

import json
import re
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

from evals.core.rubric import Rubric
from evals.core.types import EvalSpec, GraphRun, Score

_NAME = "dashboard_insights"


def _item_input(item: Any) -> Any:
    if isinstance(item, dict):
        return item.get("input")
    return getattr(item, "input", None)


async def _seeded_dashboard_insights_adapter(item: Any) -> GraphRun:
    """Return the seeded generated output from one dataset item.

    The dashboard insight eval closes the loop on deterministic structure and
    grounding. The dataset stores anonymized source counts and the generated
    candidate payload so this spec can run without external LLM credentials.
    """

    item_input = _item_input(item)
    output: Any = {}
    if isinstance(item_input, Mapping):
        output = item_input.get("generated_output", {})
    return GraphRun(input=item_input, output=output, events=[], trace_id=None)


@dataclass(frozen=True)
class DashboardInsightsStructuralJudge:
    """Deterministic dashboard-insight judge for labels, counts, and grounding."""

    async def score(
        self,
        *,
        run: GraphRun,
        rubric: Rubric,
        expected_output: object,
    ) -> list[Score]:
        expected = _mapping(expected_output)
        output = _mapping(run.output)
        source_counts = _source_counts(expected, run.input)
        query_count = _int_value(source_counts.get("query_count"))
        unanswered_count = _int_value(source_counts.get("unanswered_count"))
        topic_counts = _count_map(source_counts.get("topics") or source_counts.get("topic_counts"))
        risk_counts = _count_map(source_counts.get("risks") or source_counts.get("risk_counts"))
        topic_counts_known = "topics" in source_counts or "topic_counts" in source_counts
        risk_counts_known = "risks" in source_counts or "risk_counts" in source_counts
        source_ids = _string_set(source_counts.get("source_message_ids"))

        topic_labels = _labels(output.get("topic_breakdown"))
        expected_topics = _string_set(expected.get("expected_topic_labels"))
        risk_labels = _labels(output.get("risk_breakdown"))
        expected_risks = _string_set(expected.get("expected_risk_labels"))

        topic_ok = expected_topics.issubset(topic_labels)
        risk_ok = expected_risks.issubset(risk_labels)
        metric_errors = _metric_errors(
            output,
            query_count,
            topic_counts,
            risk_counts,
            topic_counts_known,
            risk_counts_known,
        )
        source_errors = _source_errors(output, query_count, source_ids)
        unanswered_ok = _unanswered_ok(output, unanswered_count, source_ids)

        return [
            _score(
                rubric.name,
                "topic_labels",
                topic_ok,
                "expected topic labels present",
                f"missing topic labels: {sorted(expected_topics - topic_labels)}",
            ),
            _score(
                rubric.name,
                "risk_labels",
                risk_ok,
                "expected risk labels present",
                f"missing risk labels: {sorted(expected_risks - risk_labels)}",
            ),
            _score(
                rubric.name,
                "metric_grounding",
                not metric_errors,
                "generated counts are bounded by source counts",
                "; ".join(metric_errors),
            ),
            _score(
                rubric.name,
                "source_grounding",
                not source_errors,
                "source message IDs are present and allowed",
                "; ".join(source_errors),
            ),
            _score(
                rubric.name,
                "unanswered_coverage",
                unanswered_ok,
                "unanswered output matches seeded unanswered data",
                "missing unanswered coverage or includes ungrounded unanswered IDs",
            ),
        ]


def _score(
    rubric_name: str,
    suffix: str,
    passed: bool,
    pass_comment: str,
    fail_comment: str,
) -> Score:
    return Score(
        name=f"{rubric_name}_{suffix}",
        value=1.0 if passed else 0.0,
        comment=pass_comment if passed else fail_comment,
    )


def _mapping(value: object) -> Mapping[str, Any]:
    if isinstance(value, Mapping):
        return value
    if hasattr(value, "model_dump"):
        dumped = value.model_dump()
        return dumped if isinstance(dumped, Mapping) else {}
    if isinstance(value, str):
        try:
            decoded = json.loads(value)
        except json.JSONDecodeError:
            return {}
        return decoded if isinstance(decoded, Mapping) else {}
    return {}


def _source_counts(expected: Mapping[str, Any], run_input: Any) -> Mapping[str, Any]:
    expected_counts = expected.get("source_counts")
    if isinstance(expected_counts, Mapping):
        return expected_counts
    input_counts = _mapping(run_input).get("source_counts")
    return input_counts if isinstance(input_counts, Mapping) else {}


def _int_value(value: object) -> int:
    if isinstance(value, bool):
        return int(value)
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        return int(value)
    if isinstance(value, str) and value.isdecimal():
        return int(value)
    return 0


def _string_set(value: object) -> set[str]:
    if not isinstance(value, list | tuple | set):
        return set()
    return {str(item).strip().lower() for item in value if str(item).strip()}


def _count_map(value: object) -> dict[str, int]:
    if not isinstance(value, Mapping):
        return {}
    return {str(label).strip().lower(): _int_value(count) for label, count in value.items()}


def _labels(value: object) -> set[str]:
    labels: set[str] = set()
    if not isinstance(value, list):
        return labels
    for item in value:
        if not isinstance(item, Mapping):
            continue
        label = str(item.get("label", "")).strip().lower()
        if label:
            labels.add(label)
    return labels


def _breakdown_counts(value: object) -> list[tuple[str, int]]:
    counts: list[tuple[str, int]] = []
    if not isinstance(value, list):
        return counts
    for item in value:
        if not isinstance(item, Mapping):
            continue
        label = str(item.get("label", "")).strip().lower()
        count = _int_value(item.get("count"))
        if label:
            counts.append((label, count))
    return counts


def _metric_errors(
    output: Mapping[str, Any],
    query_count: int,
    topic_counts: dict[str, int],
    risk_counts: dict[str, int],
    topic_counts_known: bool,
    risk_counts_known: bool,
) -> list[str]:
    errors: list[str] = []
    errors.extend(
        _count_errors(
            field_name="topic",
            generated=_breakdown_counts(output.get("topic_breakdown")),
            source_counts=topic_counts,
            source_counts_known=topic_counts_known,
            query_count=query_count,
        )
    )
    errors.extend(
        _count_errors(
            field_name="risk",
            generated=_breakdown_counts(output.get("risk_breakdown")),
            source_counts=risk_counts,
            source_counts_known=risk_counts_known,
            query_count=query_count,
        )
    )
    errors.extend(_headline_metric_errors(output.get("headline_cards"), query_count))
    unanswered_generated = len(_list(output.get("unanswered_questions")))
    if unanswered_generated > query_count:
        errors.append(
            f"unanswered_questions count {unanswered_generated} exceeds query_count {query_count}"
        )
    return errors


def _count_errors(
    *,
    field_name: str,
    generated: list[tuple[str, int]],
    source_counts: dict[str, int],
    source_counts_known: bool,
    query_count: int,
) -> list[str]:
    errors: list[str] = []
    for label, generated_count in generated:
        source_limit = source_counts.get(label)
        if generated_count < 0:
            errors.append(f"{field_name} '{label}' count {generated_count} is negative")
            continue
        if source_counts_known and source_limit is None:
            errors.append(f"{field_name} label '{label}' is not in source counts")
            continue
        limit = source_limit if source_limit is not None else query_count
        if generated_count > limit:
            errors.append(
                f"{field_name} '{label}' count {generated_count} exceeds source count {limit}"
            )
    return errors


def _headline_metric_errors(value: object, query_count: int) -> list[str]:
    errors: list[str] = []
    for item in _list(value):
        if not isinstance(item, Mapping):
            continue
        candidates = [item.get("count"), item.get("value")]
        for candidate in candidates:
            for generated_count in _numbers(candidate):
                if generated_count > query_count:
                    errors.append(
                        f"headline metric {generated_count} exceeds query_count {query_count}"
                    )
    return errors


def _numbers(value: object) -> list[int]:
    if isinstance(value, bool):
        return []
    if isinstance(value, int | float):
        return [int(value)]
    if isinstance(value, str):
        return [int(match) for match in re.findall(r"\b\d+\b", value)]
    return []


def _source_errors(
    output: Mapping[str, Any],
    query_count: int,
    source_ids: set[str],
) -> list[str]:
    errors: list[str] = []
    output_source_ids = _string_set(output.get("source_message_ids"))
    if query_count > 0 and not output_source_ids:
        errors.append("source_message_ids is empty for a non-empty source window")
    unknown_source_ids = output_source_ids - source_ids if source_ids else set()
    if unknown_source_ids:
        errors.append(f"unknown source_message_ids: {sorted(unknown_source_ids)}")

    unanswered_ids = _message_ids(output.get("unanswered_questions"))
    unknown_unanswered_ids = unanswered_ids - source_ids if source_ids else set()
    if unknown_unanswered_ids:
        errors.append(f"unknown unanswered message IDs: {sorted(unknown_unanswered_ids)}")
    return errors


def _unanswered_ok(
    output: Mapping[str, Any],
    unanswered_count: int,
    source_ids: set[str],
) -> bool:
    unanswered_items = _list(output.get("unanswered_questions"))
    if unanswered_count == 0:
        return not unanswered_items
    if not unanswered_items:
        return False
    unanswered_ids = _message_ids(unanswered_items)
    return not source_ids or unanswered_ids.issubset(source_ids)


def _message_ids(value: object) -> set[str]:
    ids: set[str] = set()
    for item in _list(value):
        if not isinstance(item, Mapping):
            continue
        message_id = str(item.get("message_id", "")).strip().lower()
        if message_id:
            ids.add(message_id)
    return ids


def _list(value: object) -> list[object]:
    return value if isinstance(value, list) else []


SPEC = EvalSpec(
    name=_NAME,
    dataset_path=f"evals/datasets/{_NAME}.yaml",
    adapter=_seeded_dashboard_insights_adapter,
    rubrics=[f"evals/rubrics/{_NAME}.yaml"],
    judge=DashboardInsightsStructuralJudge(),
    thresholds={
        "dashboard_insights_topic_labels": 1.0,
        "dashboard_insights_risk_labels": 1.0,
        "dashboard_insights_metric_grounding": 1.0,
        "dashboard_insights_source_grounding": 1.0,
        "dashboard_insights_unanswered_coverage": 1.0,
    },
)
