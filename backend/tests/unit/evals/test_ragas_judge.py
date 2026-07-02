from __future__ import annotations

import os

import pytest

from evals.core.judges import ragas as ragas_module
from evals.core.rubric import Criterion, Rubric
from evals.core.types import GraphRun


def test_ragas_judge_disables_ragas_usage_tracking_before_import(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    seen_tracking_values: list[str | None] = []

    def fake_ragas() -> dict[str, object]:
        seen_tracking_values.append(os.environ.get("RAGAS_DO_NOT_TRACK"))
        return {
            "LangchainLLMWrapper": lambda model: model,
            "LangchainEmbeddingsWrapper": lambda embeddings: embeddings,
        }

    monkeypatch.delenv("RAGAS_DO_NOT_TRACK", raising=False)
    monkeypatch.setattr(ragas_module, "_ragas", fake_ragas)

    ragas_module.RagasJudge(chat_model=object())._ensure_ready()

    assert seen_tracking_values == ["true"]
    assert os.environ["RAGAS_DO_NOT_TRACK"] == "true"


class _FakeSingleTurnSample:
    def __init__(self, **kwargs: object) -> None:
        self.kwargs = kwargs


class _RaisingMetric:
    async def single_turn_ascore(self, sample: _FakeSingleTurnSample) -> float:
        raise AssertionError("context-dependent metric should not be called")


def _fake_context_metric_ragas() -> dict[str, object]:
    return {
        "SingleTurnSample": _FakeSingleTurnSample,
        "LangchainLLMWrapper": lambda model: model,
        "LangchainEmbeddingsWrapper": lambda embeddings: embeddings,
        "ContextPrecision": lambda llm: _RaisingMetric(),
        "ContextRecall": lambda llm: _RaisingMetric(),
        "Faithfulness": lambda llm: _RaisingMetric(),
        "ResponseRelevancy": lambda llm, embeddings: _RaisingMetric(),
        "AspectCritic": lambda name, definition, llm: _RaisingMetric(),
    }


def _context_rubric() -> Rubric:
    return Rubric(
        name="rag",
        description="RAG metrics",
        criteria=[
            Criterion(name="context_precision", description="precision"),
            Criterion(name="context_recall", description="recall"),
            Criterion(name="faithfulness", description="faithfulness"),
        ],
    )


@pytest.mark.asyncio
async def test_ragas_judge_skips_context_metrics_when_no_context_expected(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(ragas_module, "_ragas", _fake_context_metric_ragas)

    scores = await ragas_module.RagasJudge(chat_model=object()).score(
        run=GraphRun(input={"question": "help"}, output={"answer": "safe refusal"}),
        rubric=_context_rubric(),
        expected_output={"expected_source_ids": []},
    )

    assert {score.name: score.value for score in scores} == {
        "context_precision": "skipped",
        "context_recall": "skipped",
        "faithfulness": "skipped",
    }
    assert all(score.data_type == "CATEGORICAL" for score in scores)
    assert all("no retrieved contexts" in (score.comment or "") for score in scores)


@pytest.mark.asyncio
async def test_ragas_judge_scores_zero_when_expected_context_missing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(ragas_module, "_ragas", _fake_context_metric_ragas)

    scores = await ragas_module.RagasJudge(chat_model=object()).score(
        run=GraphRun(input={"question": "what is the NIL policy?"}, output={"answer": "I do not know"}),
        rubric=_context_rubric(),
        expected_output={"expected_source_ids": ["nil_policy"]},
    )

    assert {score.name: score.value for score in scores} == {
        "context_precision": 0.0,
        "context_recall": 0.0,
        "faithfulness": 0.0,
    }
    assert all(score.data_type == "NUMERIC" for score in scores)
    assert all("expected context was missing" in (score.comment or "") for score in scores)
