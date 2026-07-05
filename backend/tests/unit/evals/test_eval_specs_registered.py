from __future__ import annotations

from evals.core.types import EvalSpec
from evals.specs import REGISTRY
from evals.specs.admin_chat import SPEC as admin_chat_spec
from evals.specs.athlete_chat import SPEC as athlete_chat_spec
from evals.specs.conversation_title import SPEC as conversation_title_spec
from evals.specs.dashboard_insights import SPEC as dashboard_insights_spec


def test_playbook_executor_specs_export_parent_registry_ready_specs() -> None:
    specs = [athlete_chat_spec, admin_chat_spec, conversation_title_spec]

    assert all(isinstance(spec, EvalSpec) for spec in specs)
    assert [spec.name for spec in specs] == [
        "athlete_chat",
        "admin_chat",
        "conversation_title",
    ]
    assert [spec.dataset_path for spec in specs] == [
        "evals/datasets/athlete_chat.yaml",
        "evals/datasets/admin_chat.yaml",
        "evals/datasets/conversation_title.yaml",
    ]


def test_playbook_executor_specs_use_expected_rubric_contracts() -> None:
    assert athlete_chat_spec.rubrics == [
        "evals/rubrics/athlete_chat.yaml",
        "evals/rubrics/athlete_chat_deterministic.yaml",
        "evals/rubrics/rag_retrieval.yaml",
        "evals/rubrics/rag_generation.yaml",
    ]
    assert admin_chat_spec.rubrics == [
        "evals/rubrics/admin_chat.yaml",
        "evals/rubrics/admin_chat_deterministic.yaml",
    ]
    assert conversation_title_spec.rubrics == [
        "evals/rubrics/conversation_title.yaml",
        "evals/rubrics/conversation_title_deterministic.yaml",
    ]
    assert callable(athlete_chat_spec.adapter)
    assert callable(admin_chat_spec.adapter)
    assert callable(conversation_title_spec.adapter)


def test_playbook_release_registry_contains_agent_specs() -> None:
    assert list(REGISTRY) == [
        "athlete_chat",
        "admin_chat",
        "dashboard_insights",
        "conversation_title",
    ]


def test_playbook_release_specs_set_target_thresholds() -> None:
    assert athlete_chat_spec.thresholds == {
        "retrieval_hit": 0.85,
        "citation_integrity": 1.0,
        "expected_behavior": 0.95,
        "source_freshness": 1.0,
        "privacy_leakage": 1.0,
        "athlete_accuracy": 4.25,
        "athlete_concision": 4.0,
        "athlete_warmth": 4.0,
        "context_precision": 0.75,
        "context_recall": 0.80,
        "faithfulness": 0.90,
        "answer_relevancy": 0.80,
    }
    assert admin_chat_spec.thresholds == {
        "expected_behavior": 0.95,
        "admin_reference_integrity": 1.0,
        "privacy_leakage": 1.0,
        "admin_usefulness": 4.0,
        "admin_specificity": 4.0,
        "admin_scope_control": 4.25,
    }
    assert conversation_title_spec.thresholds == {
        "expected_answer": 0.9,
        "privacy_leakage": 1.0,
        "title_relevance": 4.0,
        "title_brevity": 4.0,
        "title_privacy": 4.5,
    }
    assert dashboard_insights_spec.thresholds == {
        "dashboard_insights_topic_labels": 1.0,
        "dashboard_insights_risk_labels": 1.0,
        "dashboard_insights_metric_grounding": 1.0,
        "dashboard_insights_source_grounding": 1.0,
        "dashboard_insights_unanswered_coverage": 1.0,
    }
