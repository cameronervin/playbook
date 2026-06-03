"""Eval spec: the example workflow chain (LLM-as-judge + Ragas RAG metrics).

The example chain is KB-using, so it runs the LLM judge on its content rubric
(``example.yaml``) AND the Ragas judge on the shared RAG rubrics
(``rag_retrieval.yaml`` / ``rag_generation.yaml``) via a CompositeJudge.
"""

from __future__ import annotations

from evals.core.graph_env import get_example_chains
from evals.core.types import EvalSpec
from evals.specs._chain_adapter import make_chain_adapter
from evals.specs._judges import kb_composite_judge

_NAME = "example"

SPEC = EvalSpec(
    name=_NAME,
    dataset_path=f"evals/datasets/{_NAME}.yaml",
    adapter=make_chain_adapter(get_example_chains, "example", capture_kb=True),
    rubrics=[
        f"evals/rubrics/{_NAME}.yaml",
        "evals/rubrics/rag_retrieval.yaml",
        "evals/rubrics/rag_generation.yaml",
    ],
    judge=kb_composite_judge(_NAME),
    thresholds={},
)
