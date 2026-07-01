from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import yaml

from evals.core.validation import (
    KB_SOURCE_FIXTURE_MINIMUM,
    REQUIRED_CATEGORY_MINIMUMS,
    REQUIRED_DATASET_MINIMUMS,
    validate_dataset_file,
    validate_specs,
)


def _dataset_item(case_id: str, category: str) -> dict[str, object]:
    return {
        "input": {"question": f"What should the athlete know about {category}?"},
        "expected_output": f"A grounded {category} answer.",
        "metadata": {"id": case_id, "category": category},
    }


def _write_yaml(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(yaml.safe_dump(payload, sort_keys=False), encoding="utf-8")


def _minimum_dataset_items(dataset_name: str) -> list[dict[str, object]]:
    categories = list(REQUIRED_CATEGORY_MINIMUMS[dataset_name])
    minimum = REQUIRED_DATASET_MINIMUMS.get(dataset_name, len(categories))
    items: list[dict[str, object]] = []
    for index in range(minimum):
        category = categories[index % len(categories)]
        items.append(_dataset_item(f"{category}-case-{index}", category))
    return items


def test_validate_dataset_file_accepts_complete_required_category_set(
    tmp_path: Path,
) -> None:
    dataset_path = tmp_path / "athlete_chat.yaml"
    _write_yaml(dataset_path, _minimum_dataset_items("athlete_chat"))

    issues = validate_dataset_file(dataset_path, dataset_name="athlete_chat")

    assert issues == []


def test_validate_dataset_file_reports_schema_and_sensitive_field_issues(
    tmp_path: Path,
) -> None:
    dataset_path = tmp_path / "athlete_chat.yaml"
    _write_yaml(
        dataset_path,
        [
            {
                "input": {
                    "question": "Can I disclose this NIL deal?",
                    "email": "athlete@example.test",
                },
                "metadata": {"id": "nil-001", "category": "nil"},
            }
        ],
    )

    issues = validate_dataset_file(dataset_path, dataset_name="athlete_chat")

    messages = [issue.message for issue in issues]
    assert "items[0].expected_output is required; add the expected answer or refusal." in messages
    assert any("items[0].input.email" in message and "redact" in message for message in messages)


def test_validate_dataset_file_reports_duplicate_metadata_ids(tmp_path: Path) -> None:
    dataset_path = tmp_path / "admin_chat.yaml"
    _write_yaml(
        dataset_path,
        [
            _dataset_item("analytics-001", "analytics_summary"),
            _dataset_item("analytics-001", "dashboard_insights"),
        ],
    )

    issues = validate_dataset_file(dataset_path, dataset_name="admin_chat")

    assert any(
        "duplicate metadata.id 'analytics-001'" in issue.message
        and "items[0].metadata.id" in issue.message
        for issue in issues
    )


def test_validate_dataset_file_enforces_category_minimums_for_playbook_datasets(
    tmp_path: Path,
) -> None:
    for dataset_name in ("athlete_chat", "admin_chat", "dashboard_insights"):
        categories = list(REQUIRED_CATEGORY_MINIMUMS[dataset_name])
        missing_category = categories[-1]
        dataset_path = tmp_path / f"{dataset_name}.yaml"
        _write_yaml(
            dataset_path,
            [
                _dataset_item(f"{category}-case", category)
                for category in categories
                if category != missing_category
            ],
        )

        issues = validate_dataset_file(dataset_path, dataset_name=dataset_name)

        assert any(
            dataset_name in issue.message
            and missing_category in issue.message
            and "metadata.category" in issue.message
            for issue in issues
        )


def test_validate_specs_requires_playbook_kb_source_fixture(tmp_path: Path) -> None:
    dataset_path = tmp_path / "evals" / "datasets" / "dashboard_insights.yaml"
    _write_yaml(
        dataset_path,
        _minimum_dataset_items("dashboard_insights"),
    )
    spec = SimpleNamespace(name="dashboard_insights", dataset_path=str(dataset_path))

    issues = validate_specs([spec])

    assert any(
        "_fixtures/playbook_kb_sources.yaml" in issue.path
        and f"at least {KB_SOURCE_FIXTURE_MINIMUM}" in issue.message
        for issue in issues
    )


def test_validate_specs_accepts_fixture_minimum_without_langfuse(
    tmp_path: Path,
) -> None:
    dataset_path = tmp_path / "evals" / "datasets" / "dashboard_insights.yaml"
    fixture_path = dataset_path.parent / "_fixtures" / "playbook_kb_sources.yaml"
    _write_yaml(
        dataset_path,
        _minimum_dataset_items("dashboard_insights"),
    )
    _write_yaml(
        fixture_path,
        [
            {
                "id": f"kb-source-{index}",
                "title": f"Source {index}",
                "content": "Approved department guidance for a golden eval.",
            }
            for index in range(KB_SOURCE_FIXTURE_MINIMUM)
        ],
    )
    spec = SimpleNamespace(name="dashboard_insights", dataset_path=str(dataset_path))

    issues = validate_specs([spec])

    assert issues == []
