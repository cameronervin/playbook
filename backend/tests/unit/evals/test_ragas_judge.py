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


class _LowNativeMetric:
    async def single_turn_ascore(self, sample: _FakeSingleTurnSample) -> float:
        return 0.2


class _PassingAspectMetric:
    async def single_turn_ascore(self, sample: _FakeSingleTurnSample) -> float:
        return 1.0


class _PassingLLMJudge:
    def __init__(self, chat_model: object) -> None:
        self.chat_model = chat_model

    async def score(
        self,
        *,
        run: GraphRun,
        rubric: Rubric,
        expected_output: object,
    ) -> list[ragas_module.Score]:
        return [
            ragas_module.Score(
                name=criterion.name,
                value=1.0,
                data_type="NUMERIC",
                comment="fallback judge passed",
            )
            for criterion in rubric.criteria
        ]


class _FailingLLMJudge:
    def __init__(self, chat_model: object) -> None:
        self.chat_model = chat_model

    async def score(
        self,
        *,
        run: GraphRun,
        rubric: Rubric,
        expected_output: object,
    ) -> list[ragas_module.Score]:
        raise ValueError("fallback parser failed")


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


def _fake_low_generation_metric_ragas() -> dict[str, object]:
    return {
        "SingleTurnSample": _FakeSingleTurnSample,
        "LangchainLLMWrapper": lambda model: model,
        "LangchainEmbeddingsWrapper": lambda embeddings: embeddings,
        "ContextPrecision": lambda llm: _RecordingMetric(),
        "ContextRecall": lambda llm: _RecordingMetric(),
        "Faithfulness": lambda llm: _LowNativeMetric(),
        "ResponseRelevancy": lambda llm, embeddings: _LowNativeMetric(),
        "AspectCritic": lambda name, definition, llm: _PassingAspectMetric(),
    }


def _fake_low_context_recall_metric_ragas() -> dict[str, object]:
    return {
        "SingleTurnSample": _FakeSingleTurnSample,
        "LangchainLLMWrapper": lambda model: model,
        "LangchainEmbeddingsWrapper": lambda embeddings: embeddings,
        "ContextPrecision": lambda llm: _RecordingMetric(),
        "ContextRecall": lambda llm: _LowNativeMetric(),
        "Faithfulness": lambda llm: _RecordingMetric(),
        "ResponseRelevancy": lambda llm, embeddings: _RecordingMetric(),
        "AspectCritic": lambda name, definition, llm: _PassingAspectMetric(),
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


@pytest.mark.asyncio
async def test_ragas_judge_falls_back_to_aspect_for_low_generation_scores(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(ragas_module, "_ragas", _fake_low_generation_metric_ragas)
    monkeypatch.setattr(ragas_module, "LLMJudge", _PassingLLMJudge)

    scores = await ragas_module.RagasJudge(
        chat_model=object(),
        embeddings=object(),
    ).score(
        run=GraphRun(
            input={"question": "Can I accept free shoes?"},
            output={"answer": "Do not accept them unless Compliance approves first."},
            events=[
                {
                    "retriever": {
                        "documents": [
                            "Athletes should not accept free gear unless Compliance approves."
                        ]
                    }
                }
            ],
        ),
        rubric=Rubric(
            name="rag_generation",
            description="generation",
            criteria=[
                Criterion(name="faithfulness", description="grounded in context"),
                Criterion(name="answer_relevancy", description="answers the user"),
            ],
        ),
        expected_output={
            "answer_type": "grounded_answer",
            "expected_source_ids": ["src:gear#chunk-1"],
            "required_behavior": "Tell the athlete not to accept without approval.",
        },
    )

    assert {score.name: score.value for score in scores} == {
        "faithfulness": 1.0,
        "answer_relevancy": 1.0,
    }
    assert all(
        "llm_aspect_fallback_after_ragas_low_score" in (score.comment or "")
        for score in scores
    )
    assert all("native=0.200" in (score.comment or "") for score in scores)


@pytest.mark.asyncio
async def test_ragas_judge_falls_back_to_llm_for_low_context_recall(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(ragas_module, "_ragas", _fake_low_context_recall_metric_ragas)
    monkeypatch.setattr(ragas_module, "LLMJudge", _PassingLLMJudge)

    scores = await ragas_module.RagasJudge(chat_model=object()).score(
        run=GraphRun(
            input={"question": "Can I use the source?"},
            output={"answer": "Use the current policy."},
            events=[{"retriever": {"documents": ["Use the current policy."]}}],
        ),
        rubric=Rubric(
            name="rag_retrieval",
            description="retrieval",
            criteria=[Criterion(name="context_recall", description="context covers reference")],
        ),
        expected_output={
            "answer_type": "grounded_answer",
            "expected_source_ids": ["src:policy#chunk-1"],
            "required_behavior": "Use the current policy.",
        },
    )

    assert scores[0].name == "context_recall"
    assert scores[0].value == 1.0
    assert "llm_aspect_fallback_after_ragas_low_score" in (scores[0].comment or "")
    assert "native=0.200" in (scores[0].comment or "")


@pytest.mark.asyncio
async def test_ragas_judge_keeps_native_score_when_generation_fallback_fails(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(ragas_module, "_ragas", _fake_low_generation_metric_ragas)
    monkeypatch.setattr(ragas_module, "LLMJudge", _FailingLLMJudge)

    scores = await ragas_module.RagasJudge(
        chat_model=object(),
        embeddings=object(),
    ).score(
        run=GraphRun(
            input={"question": "Can I accept free shoes?"},
            output={"answer": "Do not accept them unless Compliance approves first."},
            events=[
                {
                    "retriever": {
                        "documents": [
                            "Athletes should not accept free gear unless Compliance approves."
                        ]
                    }
                }
            ],
        ),
        rubric=Rubric(
            name="rag_generation",
            description="generation",
            criteria=[Criterion(name="faithfulness", description="grounded in context")],
        ),
        expected_output={
            "answer_type": "grounded_answer",
            "expected_source_ids": ["src:gear#chunk-1"],
            "required_behavior": "Tell the athlete not to accept without approval.",
        },
    )

    assert scores[0].value == 0.2
    assert "llm_fallback_failed_after_ragas_low_score" in (scores[0].comment or "")
    assert "native=0.200" in (scores[0].comment or "")
