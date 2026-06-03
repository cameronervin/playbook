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

from __future__ import annotations

import sys
import types
from dataclasses import dataclass, field
from typing import Any

import structlog

from evals.core.rubric import Rubric
from evals.core.types import GraphRun, Score

logger = structlog.get_logger(__name__)

# Cache of lazily-imported ragas symbols, populated by _ragas().
_RAGAS: dict[str, Any] = {}


def _install_ragas_compat_shim() -> None:
    """Stub the Vertex AI paths ragas 0.4.3 hard-imports but no longer exist."""
    for mod_name, attr in (
        ("langchain_community.chat_models.vertexai", "ChatVertexAI"),
        ("langchain_community.llms.vertexai", "VertexAI"),
    ):
        try:
            __import__(mod_name)
        except Exception:  # ModuleNotFoundError on langchain-community >= 0.4
            stub = types.ModuleType(mod_name)
            setattr(stub, attr, type(attr, (), {}))
            sys.modules[mod_name] = stub
    # ragas also does `from langchain_community.llms import VertexAI`.
    try:
        import langchain_community.llms as _llms

        if not hasattr(_llms, "VertexAI"):
            _llms.VertexAI = type("VertexAI", (), {})  # type: ignore[attr-defined]
    except Exception:  # pragma: no cover - langchain_community always present with ragas
        pass


def _ragas() -> dict[str, Any]:
    """Import ragas once (after installing the compat shim) and cache its symbols."""
    if _RAGAS:
        return _RAGAS
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


@dataclass
class RagasJudge:
    """RAG retrieval/generation judge backed by injected LiteLLM-gateway models."""

    chat_model: Any  # langchain BaseChatModel (gateway-routed)
    embeddings: Any | None = None  # langchain Embeddings (gateway-routed) or None
    _llm: Any = field(default=None, init=False, repr=False)
    _emb: Any = field(default=None, init=False, repr=False)
    _ready: bool = field(default=False, init=False, repr=False)

    def _ensure_ready(self) -> None:
        """Import ragas (with shim) and wrap the models on first use — never at import."""
        if self._ready:
            return
        r = _ragas()
        self._llm = r["LangchainLLMWrapper"](self.chat_model)
        self._emb = r["LangchainEmbeddingsWrapper"](self.embeddings) if self.embeddings else None
        self._ready = True

    def _build_metrics(self, rubric: Rubric) -> list[tuple[str, Any | None]]:
        """Return (criterion_name, metric_or_None) pairs. None => skip with a note."""
        r = _ragas()
        pairs: list[tuple[str, Any | None]] = []
        for c in rubric.criteria:
            name = c.name
            if name == "faithfulness":
                pairs.append((name, r["Faithfulness"](llm=self._llm)))
            elif name == "answer_relevancy":
                if self._emb is None:
                    pairs.append((name, None))  # needs embeddings
                else:
                    pairs.append((name, r["ResponseRelevancy"](llm=self._llm, embeddings=self._emb)))
            elif name == "context_precision":
                pairs.append((name, r["ContextPrecision"](llm=self._llm)))
            elif name == "context_recall":
                pairs.append((name, r["ContextRecall"](llm=self._llm)))
            else:
                # No native metric → rubric-driven AspectCritic using the YAML description.
                pairs.append((name, r["AspectCritic"](name=name, definition=c.description, llm=self._llm)))
        return pairs

    async def score(
        self,
        *,
        run: GraphRun,
        rubric: Rubric,
        expected_output: object,
    ) -> list[Score]:
        self._ensure_ready()
        r = _ragas()
        sample = r["SingleTurnSample"](
            user_input=_question(run),
            response=_response(run),
            retrieved_contexts=_retrieved_contexts(run) or None,
            reference=str(expected_output),
        )
        scores: list[Score] = []
        for name, metric in self._build_metrics(rubric):
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
            except Exception as exc:  # one bad metric shouldn't sink the whole run
                logger.warning("ragas_metric_error", metric=name, error=str(exc), exc_info=True)
                scores.append(
                    Score(name=name, value="error", data_type="CATEGORICAL", comment=f"ragas error: {exc}")
                )
                continue
            scores.append(
                Score(name=name, value=float(value), data_type="NUMERIC", comment=f"ragas:{name}")
            )
        return scores
