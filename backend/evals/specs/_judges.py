"""Judge builders shared across specs.

Every spec uses the LLM-as-judge. KB-using specs add Ragas (retrieval +
generation) via a CompositeJudge of ScopedJudges, so the LLM judge scores the
spec's content rubric and the Ragas judge scores the shared RAG rubrics — with
no criterion double-scored.

Convention: a rubric YAML's ``name:`` must match the ScopedJudge allowlist —
the spec name for the content rubric, and "rag_retrieval" / "rag_generation"
for the shared RAG rubrics.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field

from evals.core.graph_env import get_eval_chat_model, get_eval_embeddings
from evals.core.judges import (
    CompositeJudge,
    DeterministicJudge,
    LLMJudge,
    RagasJudge,
    ScopedJudge,
)
from evals.core.judges.base import Judge
from evals.core.rubric import Rubric
from evals.core.types import GraphRun, Score

RAG_RUBRIC_NAMES = {"rag_retrieval", "rag_generation"}
RAG_RUBRIC_PATHS = ["evals/rubrics/rag_retrieval.yaml", "evals/rubrics/rag_generation.yaml"]


@dataclass
class LazyJudge:
    """Defer provider/model construction until a spec actually scores a run."""

    factory: Callable[[], Judge]
    _judge: Judge | None = field(default=None, init=False, repr=False)

    def _get(self) -> Judge:
        if self._judge is None:
            self._judge = self.factory()
        return self._judge

    async def score(
        self,
        *,
        run: GraphRun,
        rubric: Rubric,
        expected_output: object,
    ) -> list[Score]:
        return await self._get().score(
            run=run,
            rubric=rubric,
            expected_output=expected_output,
        )


def llm_judge() -> Judge:
    return LazyJudge(lambda: LLMJudge(chat_model=get_eval_chat_model()))


def kb_composite_judge(content_rubric_name: str) -> Judge:
    """LLM judge on the content rubric + Ragas judge on the RAG rubrics."""
    return LazyJudge(
        lambda: CompositeJudge(
            judges=[
                ScopedJudge(
                    judge=LLMJudge(chat_model=get_eval_chat_model()),
                    rubrics={content_rubric_name},
                ),
                ScopedJudge(
                    judge=RagasJudge(
                        chat_model=get_eval_chat_model(),
                        embeddings=get_eval_embeddings(),
                    ),
                    rubrics=set(RAG_RUBRIC_NAMES),
                ),
            ]
        )
    )


def playbook_kb_release_judge(
    *,
    content_rubric_name: str,
    deterministic_rubric_name: str,
) -> Judge:
    """LLM content + deterministic release gates + Ragas RAG metrics."""
    return LazyJudge(
        lambda: CompositeJudge(
            judges=[
                ScopedJudge(
                    judge=LLMJudge(chat_model=get_eval_chat_model()),
                    rubrics={content_rubric_name},
                ),
                ScopedJudge(
                    judge=DeterministicJudge(),
                    rubrics={deterministic_rubric_name},
                ),
                ScopedJudge(
                    judge=RagasJudge(
                        chat_model=get_eval_chat_model(),
                        embeddings=get_eval_embeddings(),
                    ),
                    rubrics=set(RAG_RUBRIC_NAMES),
                ),
            ]
        )
    )


def playbook_structural_release_judge(
    *,
    content_rubric_name: str,
    deterministic_rubric_name: str,
) -> Judge:
    """LLM content + deterministic release gates for non-RAG agent specs."""
    return LazyJudge(
        lambda: CompositeJudge(
            judges=[
                ScopedJudge(
                    judge=LLMJudge(chat_model=get_eval_chat_model()),
                    rubrics={content_rubric_name},
                ),
                ScopedJudge(
                    judge=DeterministicJudge(),
                    rubrics={deterministic_rubric_name},
                ),
            ]
        )
    )
