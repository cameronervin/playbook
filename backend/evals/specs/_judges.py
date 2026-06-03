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

from evals.core.graph_env import get_eval_chat_model, get_eval_embeddings
from evals.core.judges import CompositeJudge, LLMJudge, RagasJudge, ScopedJudge
from evals.core.judges.base import Judge

RAG_RUBRIC_NAMES = {"rag_retrieval", "rag_generation"}
RAG_RUBRIC_PATHS = ["evals/rubrics/rag_retrieval.yaml", "evals/rubrics/rag_generation.yaml"]


def llm_judge() -> Judge:
    return LLMJudge(chat_model=get_eval_chat_model())


def kb_composite_judge(content_rubric_name: str) -> Judge:
    """LLM judge on the content rubric + Ragas judge on the RAG rubrics."""
    return CompositeJudge(
        judges=[
            ScopedJudge(judge=LLMJudge(chat_model=get_eval_chat_model()), rubrics={content_rubric_name}),
            ScopedJudge(
                judge=RagasJudge(chat_model=get_eval_chat_model(), embeddings=get_eval_embeddings()),
                rubrics=set(RAG_RUBRIC_NAMES),
            ),
        ]
    )
