from __future__ import annotations

from dataclasses import dataclass, field

import pytest

from evals.core.rubric import Criterion, Rubric
from evals.core.types import GraphRun, Score
from evals.specs._judges import ExpectedAnswerTypeScopedJudge


@dataclass
class _RecordingJudge:
    calls: int = 0
    expected_outputs: list[object] = field(default_factory=list)

    async def score(
        self,
        *,
        run: GraphRun,
        rubric: Rubric,
        expected_output: object,
    ) -> list[Score]:
        self.calls += 1
        self.expected_outputs.append(expected_output)
        return [
            Score(
                name=criterion.name,
                value=4.0,
                data_type="NUMERIC",
                comment="scored",
            )
            for criterion in rubric.criteria
        ]


@pytest.mark.asyncio
async def test_expected_answer_type_scoped_judge_skips_out_of_scope_rows() -> None:
    inner = _RecordingJudge()
    judge = ExpectedAnswerTypeScopedJudge(
        judge=inner,
        rubric_name="admin_chat",
        included_answer_types={"analytics_answer"},
    )

    scores = await judge.score(
        run=GraphRun(input={}, output={}),
        rubric=Rubric(
            name="admin_chat",
            description="admin quality",
            criteria=[Criterion(name="admin_usefulness", description="useful")],
        ),
        expected_output={"answer_type": "refusal"},
    )

    assert inner.calls == 0
    assert scores[0].value == "skipped"
    assert scores[0].data_type == "CATEGORICAL"


@pytest.mark.asyncio
async def test_expected_answer_type_scoped_judge_scores_in_scope_rows() -> None:
    inner = _RecordingJudge()
    judge = ExpectedAnswerTypeScopedJudge(
        judge=inner,
        rubric_name="admin_chat",
        included_answer_types={"analytics_answer"},
    )

    scores = await judge.score(
        run=GraphRun(input={}, output={}),
        rubric=Rubric(
            name="admin_chat",
            description="admin quality",
            criteria=[Criterion(name="admin_usefulness", description="useful")],
        ),
        expected_output={"answer_type": "analytics_answer"},
    )

    assert inner.calls == 1
    assert scores[0].value == 4.0
