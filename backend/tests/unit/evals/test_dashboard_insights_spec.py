from __future__ import annotations

from types import SimpleNamespace

import pytest

from evals.core.rubric import Rubric
from evals.core.types import GraphRun
from evals.specs import REGISTRY
from evals.specs.dashboard_insights import DashboardInsightsStructuralJudge


def _rubric() -> Rubric:
    return Rubric(name="dashboard_insights", description="Dashboard insights structural checks.")


def _expected_output() -> dict[str, object]:
    return {
        "expected_topic_labels": ["nil", "compliance"],
        "expected_risk_labels": ["compliance"],
        "source_counts": {
            "query_count": 4,
            "unanswered_count": 1,
            "topics": {"nil": 3, "compliance": 1},
            "risks": {"compliance": 2},
            "source_message_ids": ["msg-1", "msg-2", "msg-3", "msg-4"],
        },
    }


@pytest.mark.asyncio
async def test_dashboard_insights_judge_accepts_grounded_expected_labels() -> None:
    judge = DashboardInsightsStructuralJudge()
    run = GraphRun(
        input={"scenario": "nil-compliance"},
        output={
            "summary": "NIL disclosure timing drove most questions.",
            "topic_breakdown": [
                {"label": "nil", "count": 3},
                {"label": "compliance", "count": 1},
            ],
            "risk_breakdown": [{"label": "compliance", "count": 2}],
            "unanswered_questions": [{"message_id": "msg-4", "reason": "unsupported"}],
            "recommended_attention_areas": ["Clarify NIL disclosure timing."],
            "source_message_ids": ["msg-1", "msg-2", "msg-4"],
        },
    )

    scores = await judge.score(run=run, rubric=_rubric(), expected_output=_expected_output())

    assert {score.name: score.value for score in scores} == {
        "dashboard_insights_topic_labels": 1.0,
        "dashboard_insights_risk_labels": 1.0,
        "dashboard_insights_metric_grounding": 1.0,
        "dashboard_insights_source_grounding": 1.0,
        "dashboard_insights_unanswered_coverage": 1.0,
    }


@pytest.mark.asyncio
async def test_dashboard_insights_judge_rejects_fabricated_counts() -> None:
    judge = DashboardInsightsStructuralJudge()
    run = GraphRun(
        input={"scenario": "fabricated-counts"},
        output={
            "summary": "NIL questions spiked to ten.",
            "topic_breakdown": [{"label": "nil", "count": 10}],
            "risk_breakdown": [{"label": "compliance", "count": 3}],
            "unanswered_questions": [{"message_id": "msg-4"}],
            "source_message_ids": ["msg-1", "msg-4"],
        },
    )

    scores = await judge.score(run=run, rubric=_rubric(), expected_output=_expected_output())

    assert next(score for score in scores if score.name == "dashboard_insights_metric_grounding").value == 0.0


@pytest.mark.asyncio
async def test_dashboard_insights_judge_rejects_missing_grounding() -> None:
    judge = DashboardInsightsStructuralJudge()
    run = GraphRun(
        input={"scenario": "missing-grounding"},
        output={
            "summary": "Compliance risk is present.",
            "topic_breakdown": [{"label": "nil", "count": 2}],
            "risk_breakdown": [{"label": "compliance", "count": 1}],
            "unanswered_questions": [{"message_id": "msg-99"}],
            "source_message_ids": [],
        },
    )

    scores = await judge.score(run=run, rubric=_rubric(), expected_output=_expected_output())

    assert next(score for score in scores if score.name == "dashboard_insights_source_grounding").value == 0.0


def test_dashboard_insights_spec_is_registered() -> None:
    spec = REGISTRY["dashboard_insights"]

    assert (
        spec.name,
        spec.dataset_path,
        spec.rubrics,
        type(spec.judge),
    ) == (
        "dashboard_insights",
        "evals/datasets/dashboard_insights.yaml",
        ["evals/rubrics/dashboard_insights.yaml"],
        DashboardInsightsStructuralJudge,
    )


@pytest.mark.asyncio
async def test_dashboard_insights_adapter_reads_seeded_output() -> None:
    spec = REGISTRY["dashboard_insights"]
    item = SimpleNamespace(
        input={
            "scenario": "seeded",
            "generated_output": {"summary": "Seeded result."},
        }
    )

    run = await spec.adapter(item=item)

    assert run.output == {"summary": "Seeded result."}
