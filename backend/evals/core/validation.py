"""Offline validation for Playbook eval dataset YAML files.

The eval harness keeps YAML datasets as the source of truth, while Langfuse is
only a sync/run target. This module validates the on-disk files without touching
Langfuse so dataset builders, CI, and future CLI commands can fail fast with
actionable messages before any remote sync happens.
"""

from __future__ import annotations

from collections import Counter
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

import yaml

IssueSeverity = Literal["error", "warning"]

PROMPT_FIELDS = ("question", "query", "prompt")
DATASET_ITEM_KEYS = frozenset({"input", "expected_output", "metadata"})

REQUIRED_CATEGORY_MINIMUMS: dict[str, dict[str, int]] = {
    "athlete_chat": {
        "nil": 1,
        "compliance": 1,
        "process": 1,
        "unknown": 1,
        "conflict": 1,
        "emergency": 1,
        "sensitive": 1,
    },
    "admin_chat": {
        "analytics_summary": 1,
        "dashboard_insights": 1,
        "authorized_records": 1,
        "out_of_scope": 1,
    },
    "dashboard_insights": {
        "nil": 1,
        "compliance": 1,
        "recruiting": 1,
        "unanswered": 1,
    },
}
REQUIRED_DATASET_MINIMUMS: dict[str, int] = {
    "athlete_chat": 74,
    "admin_chat": 32,
    "dashboard_insights": 12,
}

KB_SOURCE_FIXTURE_RELATIVE_PATH = Path("_fixtures") / "playbook_kb_sources.yaml"
KB_SOURCE_FIXTURE_MINIMUM = 18

_FORBIDDEN_SENSITIVE_FIELDS = frozenset(
    {
        "access_token",
        "api_key",
        "athlete_id",
        "athlete_name",
        "authorization",
        "bearer_token",
        "birthdate",
        "client_secret",
        "cookie",
        "date_of_birth",
        "dob",
        "email",
        "email_address",
        "first_name",
        "full_name",
        "id_token",
        "last_name",
        "oauth_token",
        "passcode",
        "password",
        "phone",
        "phone_number",
        "refresh_token",
        "secret",
        "session_token",
        "social_security_number",
        "ssn",
        "student_id",
    }
)
_FORBIDDEN_SENSITIVE_SUFFIXES = ("_api_key", "_secret", "_token")


@dataclass(frozen=True)
class ValidationIssue:
    """One offline validation finding with enough context to fix the YAML."""

    severity: IssueSeverity
    path: str
    message: str


def validate_specs(specs: Iterable[object]) -> list[ValidationIssue]:
    """Validate all registered specs' datasets plus shared KB source fixtures."""

    issues: list[ValidationIssue] = []
    dataset_dirs: list[Path] = []

    for spec in specs:
        dataset_path = getattr(spec, "dataset_path", None)
        dataset_name = str(getattr(spec, "name", "") or "")
        if not dataset_path:
            issues.append(
                ValidationIssue(
                    severity="error",
                    path=dataset_name or "<unknown spec>",
                    message=(
                        "spec is missing dataset_path; add the YAML path before "
                        "running dataset validation."
                    ),
                )
            )
            continue

        resolved_dataset_path = _resolve_repo_path(Path(str(dataset_path)))
        dataset_dirs.append(resolved_dataset_path.parent)
        issues.extend(
            validate_dataset_file(
                resolved_dataset_path,
                dataset_name=dataset_name or resolved_dataset_path.stem,
            )
        )

    fixture_path = _fixture_path(dataset_dirs)
    issues.extend(validate_kb_source_fixture(fixture_path))
    return issues


def validate_dataset_file(
    dataset_path: str | Path,
    *,
    dataset_name: str | None = None,
) -> list[ValidationIssue]:
    """Validate one eval dataset YAML file without network or Langfuse access."""

    path = _resolve_repo_path(Path(dataset_path))
    name = dataset_name or path.stem
    issues: list[ValidationIssue] = []

    loaded, load_issues = _load_yaml(path, description=f"{name} dataset")
    if load_issues:
        return load_issues
    if not isinstance(loaded, list):
        return [
            ValidationIssue(
                severity="error",
                path=str(path),
                message=(
                    f"{name} dataset must be a YAML list of items; wrap cases in "
                    "a top-level '-' list."
                ),
            )
        ]
    if not loaded:
        issues.append(
            ValidationIssue(
                severity="error",
                path=str(path),
                message=f"{name} dataset is empty; add at least one eval case.",
            )
        )
    minimum_count = REQUIRED_DATASET_MINIMUMS.get(name)
    if minimum_count is not None and len(loaded) < minimum_count:
        issues.append(
            ValidationIssue(
                severity="error",
                path=str(path),
                message=(
                    f"{name} dataset must contain at least {minimum_count} "
                    f"reviewed cases; found {len(loaded)}."
                ),
            )
        )

    category_counts: Counter[str] = Counter()
    seen_ids: dict[str, str] = {}

    for index, item in enumerate(loaded):
        item_path = f"items[{index}]"
        issues.extend(_sensitive_field_issues(path, item, item_path))
        if not isinstance(item, Mapping):
            issues.append(
                ValidationIssue(
                    severity="error",
                    path=str(path),
                    message=(
                        f"{item_path} must be a mapping with input, expected_output, "
                        "and metadata."
                    ),
                )
            )
            continue

        issues.extend(_item_schema_issues(path, item, item_path))
        metadata = item.get("metadata")
        if not isinstance(metadata, Mapping):
            continue

        case_id = _non_empty_string(metadata.get("id"))
        if case_id:
            id_path = f"{item_path}.metadata.id"
            first_path = seen_ids.get(case_id)
            if first_path is not None:
                issues.append(
                    ValidationIssue(
                        severity="error",
                        path=str(path),
                        message=(
                            f"duplicate metadata.id '{case_id}' at {id_path}; first "
                            f"defined at {first_path}. Use a unique stable id so "
                            "reports point to exactly one eval case."
                        ),
                    )
                )
            else:
                seen_ids[case_id] = id_path

        category = _non_empty_string(metadata.get("category"))
        if category:
            category_counts[category.lower()] += 1

    issues.extend(_category_minimum_issues(path, name, category_counts))
    return issues


def validate_kb_source_fixture(fixture_path: str | Path) -> list[ValidationIssue]:
    """Validate the shared offline KB source fixture file and minimum count."""

    path = _resolve_repo_path(Path(fixture_path))
    loaded, load_issues = _load_yaml(path, description="KB source fixture")
    if load_issues:
        if not path.exists():
            return [
                ValidationIssue(
                    severity="error",
                    path=str(path),
                    message=(
                        f"{KB_SOURCE_FIXTURE_RELATIVE_PATH} is required with at "
                        f"least {KB_SOURCE_FIXTURE_MINIMUM} redacted KB source "
                        "fixtures; create it so retrieval and citation evals can "
                        "run offline."
                    ),
                )
            ]
        return load_issues

    issues: list[ValidationIssue] = []
    issues.extend(_sensitive_field_issues(path, loaded, "sources"))
    if not isinstance(loaded, list):
        return [
            ValidationIssue(
                severity="error",
                path=str(path),
                message=(
                    f"{KB_SOURCE_FIXTURE_RELATIVE_PATH} must be a YAML list of "
                    "redacted KB source fixtures."
                ),
            )
        ]

    if len(loaded) < KB_SOURCE_FIXTURE_MINIMUM:
        issues.append(
            ValidationIssue(
                severity="error",
                path=str(path),
                message=(
                    f"{KB_SOURCE_FIXTURE_RELATIVE_PATH} must contain at least "
                    f"{KB_SOURCE_FIXTURE_MINIMUM} source fixtures; found "
                    f"{len(loaded)}. Add redacted NIL/compliance/process sources "
                    "for retrieval and citation evals."
                ),
            )
        )

    seen_ids: dict[str, str] = {}
    for index, source in enumerate(loaded):
        source_path = f"sources[{index}]"
        if not isinstance(source, Mapping):
            issues.append(
                ValidationIssue(
                    severity="error",
                    path=str(path),
                    message=f"{source_path} must be a mapping with id, title, and content.",
                )
            )
            continue
        source_id = _non_empty_string(source.get("id") or source.get("source_id"))
        if not source_id:
            issues.append(
                ValidationIssue(
                    severity="error",
                    path=str(path),
                    message=f"{source_path}.id is required for fixture traceability.",
                )
            )
        elif source_id in seen_ids:
            issues.append(
                ValidationIssue(
                    severity="error",
                    path=str(path),
                    message=(
                        f"duplicate fixture id '{source_id}' at {source_path}.id; "
                        f"first defined at {seen_ids[source_id]}."
                    ),
                )
            )
        else:
            seen_ids[source_id] = f"{source_path}.id"

        if not _non_empty_string(source.get("title")):
            issues.append(
                ValidationIssue(
                    severity="error",
                    path=str(path),
                    message=f"{source_path}.title is required for fixture review.",
                )
            )
        if not _fixture_content(source):
            issues.append(
                ValidationIssue(
                    severity="error",
                    path=str(path),
                    message=(
                        f"{source_path}.content is required; add redacted KB text "
                        "or one of body/text with equivalent content."
                    ),
                )
            )

    return issues


def _load_yaml(path: Path, *, description: str) -> tuple[object, list[ValidationIssue]]:
    if not path.exists():
        return None, [
            ValidationIssue(
                severity="error",
                path=str(path),
                message=f"{description} file is missing; create {path}.",
            )
        ]
    try:
        with open(path, encoding="utf-8") as file_handle:
            return yaml.safe_load(file_handle) or [], []
    except yaml.YAMLError as exc:
        return None, [
            ValidationIssue(
                severity="error",
                path=str(path),
                message=f"{description} has invalid YAML: {exc}. Fix the syntax.",
            )
        ]


def _item_schema_issues(
    path: Path,
    item: Mapping[str, object],
    item_path: str,
) -> list[ValidationIssue]:
    issues: list[ValidationIssue] = []
    unknown_keys = sorted(str(key) for key in set(item) - DATASET_ITEM_KEYS)
    if unknown_keys:
        issues.append(
            ValidationIssue(
                severity="error",
                path=str(path),
                message=(
                    f"{item_path} has unsupported top-level keys {unknown_keys}; "
                    "move case data under input, expected_output, or metadata so "
                    "dataset sync preserves it."
                ),
            )
        )

    input_obj = item.get("input")
    if "input" not in item:
        issues.append(
            ValidationIssue(
                severity="error",
                path=str(path),
                message=f"{item_path}.input is required; add the prompt and chain state.",
            )
        )
    elif not isinstance(input_obj, Mapping):
        issues.append(
            ValidationIssue(
                severity="error",
                path=str(path),
                message=f"{item_path}.input must be a mapping.",
            )
        )
    elif not any(_non_empty_string(input_obj.get(field)) for field in PROMPT_FIELDS):
        joined_fields = ", ".join(PROMPT_FIELDS)
        issues.append(
            ValidationIssue(
                severity="error",
                path=str(path),
                message=(
                    f"{item_path}.input must include one non-empty prompt field: "
                    f"{joined_fields}."
                ),
            )
        )

    if "expected_output" not in item or item.get("expected_output") is None:
        issues.append(
            ValidationIssue(
                severity="error",
                path=str(path),
                message=(
                    f"{item_path}.expected_output is required; add the expected "
                    "answer or refusal."
                ),
            )
        )
    elif item.get("expected_output") == "":
        issues.append(
            ValidationIssue(
                severity="error",
                path=str(path),
                message=(
                    f"{item_path}.expected_output must not be empty; add the "
                    "expected answer or refusal."
                ),
            )
        )

    metadata = item.get("metadata")
    if "metadata" not in item:
        issues.append(
            ValidationIssue(
                severity="error",
                path=str(path),
                message=(
                    f"{item_path}.metadata is required; add id and category for "
                    "traceability and coverage checks."
                ),
            )
        )
    elif not isinstance(metadata, Mapping):
        issues.append(
            ValidationIssue(
                severity="error",
                path=str(path),
                message=f"{item_path}.metadata must be a mapping.",
            )
        )
    else:
        if not _non_empty_string(metadata.get("id")):
            issues.append(
                ValidationIssue(
                    severity="error",
                    path=str(path),
                    message=(
                        f"{item_path}.metadata.id is required; add a stable, "
                        "human-readable case id."
                    ),
                )
            )
        if not _non_empty_string(metadata.get("category")):
            issues.append(
                ValidationIssue(
                    severity="error",
                    path=str(path),
                    message=(
                        f"{item_path}.metadata.category is required; add a "
                        "coverage category."
                    ),
                )
            )

    return issues


def _category_minimum_issues(
    path: Path,
    dataset_name: str,
    category_counts: Counter[str],
) -> list[ValidationIssue]:
    required = REQUIRED_CATEGORY_MINIMUMS.get(dataset_name)
    if required is None:
        return []

    issues: list[ValidationIssue] = []
    for category, minimum in required.items():
        actual = category_counts[category]
        if actual < minimum:
            issues.append(
                ValidationIssue(
                    severity="error",
                    path=str(path),
                    message=(
                        f"{dataset_name} requires at least {minimum} item(s) with "
                        f"metadata.category '{category}', found {actual}. Add a "
                        "golden case for this release-readiness category."
                    ),
                )
            )
    return issues


def _sensitive_field_issues(path: Path, value: object, value_path: str) -> list[ValidationIssue]:
    issues: list[ValidationIssue] = []
    if isinstance(value, Mapping):
        for raw_key, child_value in value.items():
            key = str(raw_key)
            child_path = f"{value_path}.{key}"
            if _is_forbidden_sensitive_key(key):
                issues.append(
                    ValidationIssue(
                        severity="error",
                        path=str(path),
                        message=(
                            f"{child_path} uses forbidden sensitive field '{key}'; "
                            "remove it or redact it before committing eval data."
                        ),
                    )
                )
            issues.extend(_sensitive_field_issues(path, child_value, child_path))
    elif isinstance(value, Sequence) and not isinstance(value, str | bytes | bytearray):
        for index, child_value in enumerate(value):
            issues.extend(_sensitive_field_issues(path, child_value, f"{value_path}[{index}]"))
    return issues


def _is_forbidden_sensitive_key(key: str) -> bool:
    normalized = key.lower().replace("-", "_").replace(" ", "_")
    return normalized in _FORBIDDEN_SENSITIVE_FIELDS or normalized.endswith(
        _FORBIDDEN_SENSITIVE_SUFFIXES
    )


def _non_empty_string(value: object) -> str | None:
    if not isinstance(value, str):
        return None
    stripped = value.strip()
    return stripped or None


def _fixture_content(source: Mapping[str, object]) -> str | None:
    for key in ("content", "body", "text"):
        content = _non_empty_string(source.get(key))
        if content:
            return content
    return None


def _fixture_path(dataset_dirs: list[Path]) -> Path:
    for dataset_dir in dataset_dirs:
        if dataset_dir.name == "datasets":
            return dataset_dir / KB_SOURCE_FIXTURE_RELATIVE_PATH
    return _resolve_repo_path(Path("evals") / "datasets" / KB_SOURCE_FIXTURE_RELATIVE_PATH)


def _resolve_repo_path(path: Path) -> Path:
    if path.is_absolute() or path.exists():
        return path
    backend_path = Path("backend") / path
    if path.parts and path.parts[0] == "evals" and Path("backend/evals").exists():
        return backend_path
    if backend_path.exists() or backend_path.parent.exists():
        return backend_path
    return path
