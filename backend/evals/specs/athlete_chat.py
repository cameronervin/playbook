"""Eval spec for the production athlete chat executor."""

from __future__ import annotations

from evals.core.types import EvalSpec
from evals.specs._judges import RAG_RUBRIC_PATHS, playbook_kb_release_judge
from evals.specs.playbook_adapters import make_athlete_chat_executor_adapter

_NAME = "athlete_chat"
_DETERMINISTIC_NAME = "athlete_chat_deterministic"

SPEC = EvalSpec(
    name=_NAME,
    dataset_path=f"evals/datasets/{_NAME}.yaml",
    adapter=make_athlete_chat_executor_adapter(),
    rubrics=[
        f"evals/rubrics/{_NAME}.yaml",
        f"evals/rubrics/{_DETERMINISTIC_NAME}.yaml",
        *RAG_RUBRIC_PATHS,
    ],
    judge=playbook_kb_release_judge(
        content_rubric_name=_NAME,
        deterministic_rubric_name=_DETERMINISTIC_NAME,
    ),
    thresholds={
        "retrieval_hit": 0.85,
        "citation_integrity": 1.0,
        "expected_behavior": 0.95,
        "privacy_leakage": 1.0,
    },
)
