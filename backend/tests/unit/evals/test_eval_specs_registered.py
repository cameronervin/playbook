from __future__ import annotations

from evals.core.types import EvalSpec
from evals.specs import REGISTRY
from evals.specs.admin_chat import SPEC as admin_chat_spec
from evals.specs.athlete_chat import SPEC as athlete_chat_spec
from evals.specs.conversation_title import SPEC as conversation_title_spec


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
