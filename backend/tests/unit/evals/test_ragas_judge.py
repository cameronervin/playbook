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


class _RecordingMetric:
    seen_samples: list[_FakeSingleTurnSample] = []

    async def single_turn_ascore(self, sample: _FakeSingleTurnSample) -> float:
        self.seen_samples.append(sample)
        return 1.0


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


def _fake_recording_metric_ragas() -> dict[str, object]:
    return {
        "SingleTurnSample": _FakeSingleTurnSample,
        "LangchainLLMWrapper": lambda model: model,
        "LangchainEmbeddingsWrapper": lambda embeddings: embeddings,
        "ContextPrecision": lambda llm: _RecordingMetric(),
        "ContextRecall": lambda llm: _RecordingMetric(),
        "Faithfulness": lambda llm: _RecordingMetric(),
        "ResponseRelevancy": lambda llm, embeddings: _RecordingMetric(),
        "AspectCritic": lambda name, definition, llm: _RecordingMetric(),
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


def _faithfulness_rubric() -> Rubric:
    return Rubric(
        name="rag_generation",
        description="RAG generation metrics",
        criteria=[Criterion(name="faithfulness", description="faithfulness")],
    )


def _full_ragas_rubric() -> Rubric:
    return Rubric(
        name="rag_generation",
        description="RAG generation metrics",
        criteria=[
            Criterion(name="context_precision", description="precision"),
            Criterion(name="context_recall", description="recall"),
            Criterion(name="faithfulness", description="faithfulness"),
            Criterion(name="answer_relevancy", description="relevancy"),
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


@pytest.mark.asyncio
async def test_ragas_judge_skips_all_metrics_for_non_grounded_expected_behavior(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(ragas_module, "_ragas", _fake_context_metric_ragas)

    scores = await ragas_module.RagasJudge(
        chat_model=object(),
        embeddings=object(),
    ).score(
        run=GraphRun(
            input={"question": "My teammate might hurt himself"},
            output={
                "answer": "Call 911 or campus emergency services now.",
                "answer_type": "emergency_instruction",
            },
        ),
        rubric=_full_ragas_rubric(),
        expected_output={
            "answer_type": "emergency_instruction",
            "expected_source_ids": ["src:emergency-support-card-2026#chunk-1"],
        },
    )

    assert {score.name: score.value for score in scores} == {
        "context_precision": "skipped",
        "context_recall": "skipped",
        "faithfulness": "skipped",
        "answer_relevancy": "skipped",
    }
    assert all(score.data_type == "CATEGORICAL" for score in scores)
    assert all("not a grounded RAG sample" in (score.comment or "") for score in scores)


@pytest.mark.asyncio
async def test_ragas_judge_uses_required_behavior_as_reference(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _RecordingMetric.seen_samples = []
    monkeypatch.setattr(ragas_module, "_ragas", _fake_recording_metric_ragas)

    scores = await ragas_module.RagasJudge(chat_model=object()).score(
        run=GraphRun(
            input={"question": "when do I disclose?"},
            output={"answer": "Disclose before activity."},
            events=[
                {
                    "retriever": {
                        "documents": ["NIL activity must be disclosed before activity."]
                    }
                }
            ],
        ),
        rubric=_faithfulness_rubric(),
        expected_output={
            "answer_type": "grounded_answer",
            "required_behavior": "Tell the athlete to disclose before activity.",
            "must_not": "Do not say after-the-fact reporting is fine.",
        },
    )

    assert scores[0].value == 1.0
    assert _RecordingMetric.seen_samples[0].kwargs["reference"] == (
        "Tell the athlete to disclose before activity."
    )
