"""Eval spec for the production admin analytics chat executor."""

from __future__ import annotations

from evals.core.types import EvalSpec
from evals.specs._judges import playbook_structural_release_judge
from evals.specs.playbook_adapters import make_admin_chat_executor_adapter

_NAME = "admin_chat"
_DETERMINISTIC_NAME = "admin_chat_deterministic"

SPEC = EvalSpec(
    name=_NAME,
    dataset_path=f"evals/datasets/{_NAME}.yaml",
    adapter=make_admin_chat_executor_adapter(),
    rubrics=[
        f"evals/rubrics/{_NAME}.yaml",
        f"evals/rubrics/{_DETERMINISTIC_NAME}.yaml",
    ],
    judge=playbook_structural_release_judge(
        content_rubric_name=_NAME,
        deterministic_rubric_name=_DETERMINISTIC_NAME,
    ),
    thresholds={
        "expected_behavior": 0.95,
        "admin_reference_integrity": 1.0,
        "privacy_leakage": 1.0,
        "admin_usefulness": 4.0,
        "admin_specificity": 4.0,
        "admin_scope_control": 4.25,
    },
)
