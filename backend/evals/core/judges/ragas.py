"""Ragas judge — RAG retrieval + generation metrics.

Translates a ``GraphRun`` into a Ragas ``SingleTurnSample``, runs the metrics
that match the rubric's criterion names, and translates the results back into
``Score`` objects so the runner can't tell it apart from the LLM judge.

Criterion-name → metric mapping (each yields a separately-named Score, so
retrieval and generation are reported/threshold-gated independently):

    retrieval   : context_precision, context_recall   (LLM-only)
    generation  : faithfulness                         (LLM-only)
                  answer_relevancy                     (needs embeddings)
    custom      : anything else → AspectCritic(definition=<rubric description>)

The evaluator LLM and embeddings are injected (the project's LiteLLM-gateway
``ChatOpenAI`` / ``OpenAIEmbeddings``), wrapped for Ragas.

NOTE: ragas 0.4.3 hard-imports a Vertex AI path that langchain-community 0.4.x
removed, so ``import ragas`` fails on a langchain 1.x stack. We inject a tiny
``sys.modules`` stub for the dead path before importing ragas. The stubbed
classes are never used by the metrics above. Remove the shim once ragas drops the
hard import. Imports are lazy so the harness still loads when ragas is absent.
"""

# ruff: noqa: PLC0415

from __future__ import annotations

import os
import sys
import types
from dataclasses import dataclass, field
from typing import Any

import structlog

from evals.core.judges.llm import LLMJudge
from evals.core.rubric import Criterion, Rubric
from evals.core.types import GraphRun, Score

logger = structlog.get_logger(__name__)

# Cache of lazily-imported ragas symbols, populated by _ragas().
_RAGAS: dict[str, Any] = {}
RAGAS_DO_NOT_TRACK_ENV = "RAGAS_DO_NOT_TRACK"
CONTEXT_REQUIRED_METRICS = {"context_precision", "context_recall", "faithfulness"}
GROUNDED_BEHAVIORS = {"answer", "grounded_answer", "analytics_answer"}
RAGAS_FALLBACK_FLOORS = {
    "context_recall": 0.8,
    "faithfulness": 0.9,
    "answer_relevancy": 0.8,
}


@dataclass(frozen=True, slots=True)
class MetricPlan:
    """One Ragas metric plus an optional rubric-driven fallback."""

    name: str
    metric: Any | None
    fallback_definition: str | None = None


def _install_ragas_compat_shim() -> None:
    """Stub the Vertex AI paths ragas 0.4.3 hard-imports but no longer exist."""
    for mod_name, attr in (
        ("langchain_community.chat_models.vertexai", "ChatVertexAI"),
        ("langchain_community.llms.vertexai", "VertexAI"),
    ):
        try:
            __import__(mod_name)
        except ImportError:  # ModuleNotFoundError on langchain-community >= 0.4
            stub = types.ModuleType(mod_name)
            setattr(stub, attr, type(attr, (), {}))
            sys.modules[mod_name] = stub
    # ragas also does `from langchain_community.llms import VertexAI`.
    try:
        import langchain_community.llms as _llms

        if not hasattr(_llms, "VertexAI"):
            _llms.VertexAI = type("VertexAI", (), {})  # type: ignore[attr-defined]
    except ImportError:  # pragma: no cover - langchain_community always present with ragas
        pass


def _ragas() -> dict[str, Any]:
    """Import ragas once (after installing the compat shim) and cache its symbols."""
    if _RAGAS:
        return _RAGAS
    os.environ.setdefault(RAGAS_DO_NOT_TRACK_ENV, "true")
    _install_ragas_compat_shim()
    from ragas import SingleTurnSample
    from ragas.embeddings import LangchainEmbeddingsWrapper
    from ragas.llms import LangchainLLMWrapper
    from ragas.metrics import (
        AspectCritic,
        ContextPrecision,
        ContextRecall,
        Faithfulness,
        ResponseRelevancy,
    )

    _RAGAS.update(
        SingleTurnSample=SingleTurnSample,
        LangchainLLMWrapper=LangchainLLMWrapper,
        LangchainEmbeddingsWrapper=LangchainEmbeddingsWrapper,
        AspectCritic=AspectCritic,
        ContextPrecision=ContextPrecision,
        ContextRecall=ContextRecall,
        Faithfulness=Faithfulness,
        ResponseRelevancy=ResponseRelevancy,
    )
    return _RAGAS


def _question(run: GraphRun) -> str:
    if isinstance(run.input, dict):
        return str(run.input.get("question") or run.input.get("query") or run.input)
    return str(run.input)


def _response(run: GraphRun) -> str:
    out = run.output
    if isinstance(out, dict):
        return str(out.get("answer") or out.get("text") or out)
    return str(out)


def _retrieved_contexts(run: GraphRun) -> list[str]:
    """Pull retrieved contexts out of the trajectory (see specs/_chain_adapter KB capture)."""
    retrieved: list[str] = []
    for ev in run.events:
        for node, payload in ev.items():
            if node == "retriever" and isinstance(payload, dict):
                docs = payload.get("documents") or []
                retrieved.extend(str(d) for d in docs)
    return retrieved


def _expected_source_ids(expected_output: object) -> list[str]:
    if not isinstance(expected_output, dict):
        return []
    raw = expected_output.get("expected_source_ids")
    if not isinstance(raw, list):
        return []
    return [str(source_id) for source_id in raw if str(source_id).strip()]


def _expected_behavior(expected_output: object, run: GraphRun) -> str:
    if isinstance(expected_output, dict):
        for key in ("expected_behavior", "behavior", "expected_answer_type", "answer_type"):
            value = expected_output.get(key)
            if value is not None and str(value).strip():
                return str(value).strip().lower()
    if isinstance(run.output, dict):
        value = run.output.get("answer_type")
        if value is not None and str(value).strip():
            return str(value).strip().lower()
    return ""


def _is_grounded_rag_sample(expected_output: object, run: GraphRun) -> bool:
    behavior = _expected_behavior(expected_output, run)
    return not behavior or behavior in GROUNDED_BEHAVIORS


def _reference(expected_output: object) -> str:
    """Return the compact reference text Ragas should judge against."""
    if isinstance(expected_output, dict):
        for key in ("required_behavior", "expected_behavior", "expected_answer"):
            value = expected_output.get(key)
            if isinstance(value, str) and value.strip():
                return value.strip()
    return str(expected_output)


@dataclass
class RagasJudge:
    """RAG retrieval/generation judge backed by injected LiteLLM models."""

    chat_model: Any  # langchain BaseChatModel (gateway-routed)
    embeddings: Any | None = None  # langchain Embeddings (gateway-routed) or None
    _llm: Any = field(default=None, init=False, repr=False)
    _emb: Any = field(default=None, init=False, repr=False)
    _ready: bool = field(default=False, init=False, repr=False)

    def _ensure_ready(self) -> None:
        """Import ragas (with shim) and wrap the models on first use — never at import."""
        if self._ready:
            return
        os.environ.setdefault(RAGAS_DO_NOT_TRACK_ENV, "true")
        r = _ragas()
        self._llm = r["LangchainLLMWrapper"](self.chat_model)
        self._emb = r["LangchainEmbeddingsWrapper"](self.embeddings) if self.embeddings else None
        self._ready = True

    def _build_metrics(self, rubric: Rubric) -> list[MetricPlan]:
        """Return Ragas metric plans. ``metric=None`` means skip with a note."""
        r = _ragas()
        pairs: list[MetricPlan] = []
        for c in rubric.criteria:
            name = c.name
            if name == "faithfulness":
                pairs.append(
                    MetricPlan(
                        name=name,
                        metric=r["Faithfulness"](llm=self._llm),
                        fallback_definition=c.description,
                    )
                )
            elif name == "answer_relevancy":
                if self._emb is None:
                    pairs.append(MetricPlan(name=name, metric=None))  # needs embeddings
                else:
                    pairs.append(
                        MetricPlan(
                            name=name,
                            metric=r["ResponseRelevancy"](
                                llm=self._llm,
                                embeddings=self._emb,
                            ),
                            fallback_definition=c.description,
                        )
                    )
            elif name == "context_precision":
                pairs.append(MetricPlan(name=name, metric=r["ContextPrecision"](llm=self._llm)))
            elif name == "context_recall":
                pairs.append(
                    MetricPlan(
                        name=name,
                        metric=r["ContextRecall"](llm=self._llm),
                        fallback_definition=c.description,
                    )
                )
            else:
                # No native metric → rubric-driven AspectCritic using the YAML description.
                pairs.append(
                    MetricPlan(
                        name=name,
                        metric=r["AspectCritic"](
                            name=name,
                            definition=c.description,
                            llm=self._llm,
                        ),
                    )
                )
        return pairs

    async def score(
        self,
        *,
        run: GraphRun,
        rubric: Rubric,
        expected_output: object,
    ) -> list[Score]:
        if not _is_grounded_rag_sample(expected_output, run):
            return [
                Score(
                    name=criterion.name,
                    value="skipped",
                    data_type="CATEGORICAL",
                    comment="skipped: not a grounded RAG sample",
                )
                for criterion in rubric.criteria
            ]

        self._ensure_ready()
        r = _ragas()
        retrieved_contexts = _retrieved_contexts(run)
        expects_retrieval = bool(_expected_source_ids(expected_output))
        sample = r["SingleTurnSample"](
            user_input=_question(run),
            response=_response(run),
            retrieved_contexts=retrieved_contexts or None,
            reference=_reference(expected_output),
        )
        scores: list[Score] = []
        for plan in self._build_metrics(rubric):
            name = plan.name
            metric = plan.metric
            if name in CONTEXT_REQUIRED_METRICS and not retrieved_contexts:
                if expects_retrieval:
                    scores.append(
                        Score(
                            name=name,
                            value=0.0,
                            data_type="NUMERIC",
                            comment=f"ragas:{name} expected context was missing",
                        )
                    )
                else:
                    logger.info("ragas_metric_skipped", metric=name, reason="no_retrieved_contexts")
                    scores.append(
                        Score(
                            name=name,
                            value="skipped",
                            data_type="CATEGORICAL",
                            comment="skipped: no retrieved contexts expected for this sample",
                        )
                    )
                continue
            if metric is None:
                logger.info("ragas_metric_skipped", metric=name, reason="no_embeddings")
                scores.append(
                    Score(
                        name=name,
                        value="skipped",
                        data_type="CATEGORICAL",
                        comment="skipped: no embeddings configured (set EVAL_EMBEDDINGS_MODEL)",
                    )
                )
                continue
            try:
                value = await metric.single_turn_ascore(sample)
            except Exception as exc:  # noqa: BLE001 - isolate one bad metric from the full run
                logger.warning("ragas_metric_error", metric=name, error=str(exc), exc_info=True)
                if plan.fallback_definition is not None:
                    scores.append(
                        await self._fallback_score(
                            name=name,
                            definition=plan.fallback_definition,
                            run=run,
                            expected_output=expected_output,
                            reason="error",
                            native_value=None,
                        )
                    )
                    continue
                scores.append(
                    Score(name=name, value="error", data_type="CATEGORICAL", comment=f"ragas error: {exc}")
                )
                continue
            native_value = float(value)
            fallback_floor = RAGAS_FALLBACK_FLOORS.get(name)
            if (
                plan.fallback_definition is not None
                and fallback_floor is not None
                and native_value < fallback_floor
            ):
                scores.append(
                    await self._fallback_score(
                        name=name,
                        definition=plan.fallback_definition,
                        run=run,
                        expected_output=expected_output,
                        reason="low_score",
                        native_value=native_value,
                    )
                )
                continue
            scores.append(
                Score(name=name, value=native_value, data_type="NUMERIC", comment=f"ragas:{name}")
            )
        return scores

    async def _fallback_score(
        self,
        *,
        name: str,
        definition: str,
        run: GraphRun,
        expected_output: object,
        reason: str,
        native_value: float | None,
    ) -> Score:
        native = "unavailable" if native_value is None else f"{native_value:.3f}"
        fallback_rubric = Rubric(
            name=f"ragas_{name}_fallback",
            description=f"Fallback judge for Ragas {name}.",
            # Use the harness LLM judge instead of Ragas AspectCritic here:
            # AspectCritic can turn valid escaped JSON into an empty object under
            # the OpenAI-compatible gateway, creating isolated judge errors.
            criteria=[Criterion(name=name, description=definition)],
        )
        try:
            fallback_scores = await LLMJudge(chat_model=self.chat_model).score(
                run=run,
                rubric=fallback_rubric,
                expected_output=expected_output,
            )
        except Exception as exc:  # noqa: BLE001 - fallback must not create isolated run errors
            logger.warning(
                "ragas_generation_fallback_error",
                metric=name,
                reason=reason,
                error=str(exc),
                exc_info=True,
            )
            if native_value is not None:
                return Score(
                    name=name,
                    value=native_value,
                    data_type="NUMERIC",
                    comment=(
                        f"llm_fallback_failed_after_ragas_{reason}: "
                        f"native={native}; error={exc}; ragas:{name}"
                    ),
                )
            return Score(
                name=name,
                value="error",
                data_type="CATEGORICAL",
                comment=(
                    f"llm_fallback_failed_after_ragas_{reason}: "
                    f"native={native}; error={exc}; ragas:{name}"
                ),
            )

        score = next((item for item in fallback_scores if item.name == name), None)
        if score is None or not isinstance(score.value, (int, float)) or isinstance(score.value, bool):
            if native_value is not None:
                return Score(
                    name=name,
                    value=native_value,
                    data_type="NUMERIC",
                    comment=(
                        f"llm_fallback_missing_score_after_ragas_{reason}: "
                        f"native={native}; ragas:{name}"
                    ),
                )
            return Score(
                name=name,
                value="error",
                data_type="CATEGORICAL",
                comment=(
                    f"llm_fallback_missing_score_after_ragas_{reason}: "
                    f"native={native}; ragas:{name}"
                ),
            )

        fallback_reasoning = f"; fallback_reasoning={score.comment}" if score.comment else ""
        return Score(
            name=name,
            value=float(score.value),
            data_type="NUMERIC",
            comment=(
                f"llm_aspect_fallback_after_ragas_{reason}: "
                f"native={native}; ragas:{name}{fallback_reasoning}"
            ),
        )
