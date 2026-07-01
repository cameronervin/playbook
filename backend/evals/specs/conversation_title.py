"""Eval spec for the production conversation title executor."""

from __future__ import annotations

from evals.core.types import EvalSpec
from evals.specs._judges import playbook_structural_release_judge
from evals.specs.playbook_adapters import make_conversation_title_executor_adapter

_NAME = "conversation_title"
_DETERMINISTIC_NAME = "conversation_title_deterministic"

SPEC = EvalSpec(
    name=_NAME,
    dataset_path=f"evals/datasets/{_NAME}.yaml",
    adapter=make_conversation_title_executor_adapter(),
    rubrics=[
        f"evals/rubrics/{_NAME}.yaml",
        f"evals/rubrics/{_DETERMINISTIC_NAME}.yaml",
    ],
    judge=playbook_structural_release_judge(
        content_rubric_name=_NAME,
        deterministic_rubric_name=_DETERMINISTIC_NAME,
    ),
    thresholds={
        "expected_answer": 0.9,
        "privacy_leakage": 1.0,
    },
)
