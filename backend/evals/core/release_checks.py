"""Deterministic Phase 5 release-readiness checks.

These checks intentionally avoid Langfuse, LiteLLM, databases, and live
services. They validate repo-owned release gates that should run in CI before
the optional live eval/smoke layer.
"""

from __future__ import annotations

from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

import yaml

from evals.core.validation import validate_specs
from evals.specs import REGISTRY

IssueSeverity = Literal["error", "warning"]

DEFAULT_SCAN_PATHS = (
    "backend/app",
    "kb-service/app",
    "frontend/src",
    "README.md",
    "deploy",
)
TEXT_SUFFIXES = {
    ".css",
    ".html",
    ".js",
    ".json",
    ".jsx",
    ".md",
    ".py",
    ".ts",
    ".tsx",
    ".txt",
    ".yaml",
    ".yml",
}
PROTECTED_AFFILIATION_TERMS = (
    "University of",
    "State University",
    "Duke",
    "UCLA",
    "USC",
    "Stanford",
    "Longhorns",
    "Wolverines",
    "Tar Heels",
    "Bruins",
    "Trojans",
    "Bulldogs",
    "Crimson Tide",
    "Fighting Irish",
    "official partner",
    "affiliated with",
    "on behalf of",
)
LITELLM_POLICY_PATH = Path("backend/evals/release/litellm_virtual_key_policy.yaml")
LITELLM_CONFIG_PATH = Path("deploy/litellm/config.yaml")
LITELLM_APP_ENV_PATHS = (
    Path("deploy/envs/.env.prod.example"),
    Path("deploy/envs/.env.backend.prod.example"),
    Path("deploy/envs/.env.kb-service.prod.example"),
)
EXPECTED_LITELLM_SERVICE_ALIASES = {
    "playbook-chat",
    "playbook-fast",
    "playbook-embed",
    "playbook-ocr",
    "playbook-rerank",
}
APP_LITELLM_ALIAS_ENV_KEYS = (
    "LLM_CHAT_MODEL",
    "LITELLM_EMBED_MODEL",
    "LITELLM_SUMMARY_MODEL",
    "LITELLM_RERANK_MODEL",
)
DISALLOWED_APP_PROVIDER_KEYS = (
    "OPENAI_API_KEY",
    "ANTHROPIC_API_KEY",
    "GEMINI_API_KEY",
)
OBSERVABILITY_REQUIRED_SNIPPETS = {
    Path("backend/app/core/logging_config.py"): (
        "redact_event_dict",
        "install_secret_redaction_filter",
    ),
    Path("backend/app/observability/langfuse_init.py"): (
        "mask=mask_langfuse_data",
        "source_uri",
        "prompt",
    ),
    Path("backend/app/middleware/request_context.py"): (
        "X-Request-ID",
        "http_request_completed",
    ),
    Path("kb-service/app/core/logging_config.py"): (
        "redact_event_dict",
        "install_secret_redaction_filter",
    ),
}


@dataclass(frozen=True)
class ReleaseCheckIssue:
    """One deterministic release-readiness finding."""

    severity: IssueSeverity
    path: str
    message: str


@dataclass(frozen=True)
class ReleaseCheckResult:
    """Aggregate release-check result."""

    issues: list[ReleaseCheckIssue]

    @property
    def passed(self) -> bool:
        return not any(issue.severity == "error" for issue in self.issues)

    def summary(self) -> str:
        status = "PASS" if self.passed else "FAIL"
        return f"{status} release checks ({len(self.issues)} issue(s))"


def run_release_checks(
    *,
    repo_root: Path | None = None,
    specs: Iterable[object] | None = None,
) -> ReleaseCheckResult:
    """Run all deterministic Phase 5 release-readiness checks."""
    root = repo_root or _repo_root()
    issues: list[ReleaseCheckIssue] = []
    issues.extend(_dataset_validation_issues(specs=specs))
    issues.extend(check_litellm_gateway_controls(repo_root=root))
    issues.extend(check_affiliation_copy(repo_root=root))
    issues.extend(check_observability_baseline(repo_root=root))
    issues.extend(check_rate_limit_release_config(repo_root=root))
    return ReleaseCheckResult(issues=issues)


def check_litellm_gateway_controls(*, repo_root: Path) -> list[ReleaseCheckIssue]:
    """Validate deterministic LiteLLM proxy, policy, and app-env controls."""
    aliases, issues = _litellm_model_aliases(repo_root / LITELLM_CONFIG_PATH)
    issues.extend(
        check_litellm_virtual_key_policy(
            repo_root / LITELLM_POLICY_PATH,
            allowed_aliases=aliases or None,
        )
    )
    issues.extend(_check_litellm_app_env_examples(repo_root=repo_root, allowed_aliases=aliases))
    return issues


def check_litellm_virtual_key_policy(
    policy_path: Path,
    *,
    allowed_aliases: set[str] | None = None,
) -> list[ReleaseCheckIssue]:
    """Validate the non-secret LiteLLM virtual-key budget/rate policy manifest."""
    if not policy_path.exists():
        return [
            ReleaseCheckIssue(
                severity="error",
                path=str(policy_path),
                message="LiteLLM virtual-key policy manifest is missing.",
            )
        ]

    loaded = yaml.safe_load(policy_path.read_text(encoding="utf-8"))
    if not isinstance(loaded, dict):
        return [
            ReleaseCheckIssue(
                severity="error",
                path=str(policy_path),
                message="LiteLLM virtual-key policy must be a mapping.",
            )
        ]
    keys = loaded.get("virtual_keys")
    if not isinstance(keys, list) or not keys:
        return [
            ReleaseCheckIssue(
                severity="error",
                path=str(policy_path),
                message="virtual_keys must contain at least one key policy.",
            )
        ]

    issues: list[ReleaseCheckIssue] = []
    for index, item in enumerate(keys):
        item_path = f"virtual_keys[{index}]"
        if not isinstance(item, dict):
            issues.append(
                ReleaseCheckIssue(
                    severity="error",
                    path=str(policy_path),
                    message=f"{item_path} must be a mapping.",
                )
            )
            continue
        issues.extend(_required_string(item, "name", item_path, policy_path))
        models = item.get("allowed_models")
        if not isinstance(models, list) or not all(
            isinstance(model, str) and model for model in models
        ):
            issues.append(
                ReleaseCheckIssue(
                    severity="error",
                    path=str(policy_path),
                    message=f"{item_path}.allowed_models must list model aliases.",
                )
            )
        else:
            for model in models:
                if model == "*":
                    issues.append(
                        ReleaseCheckIssue(
                            severity="error",
                            path=str(policy_path),
                            message=f"{item_path}.allowed_models must not include wildcard access.",
                        )
                    )
                if allowed_aliases is not None and model not in allowed_aliases:
                    issues.append(
                        ReleaseCheckIssue(
                            severity="error",
                            path=str(policy_path),
                            message=(
                                f"{item_path}.allowed_models entry {model} "
                                "is not defined in deploy/litellm/config.yaml."
                            ),
                        )
                    )
        issues.extend(_required_positive_number(item, "max_budget", item_path, policy_path))
        issues.extend(_required_string(item, "budget_duration", item_path, policy_path))
        issues.extend(_required_positive_number(item, "rpm_limit", item_path, policy_path))
    return issues


def _litellm_model_aliases(config_path: Path) -> tuple[set[str], list[ReleaseCheckIssue]]:
    if not config_path.exists():
        return set(), [
            ReleaseCheckIssue(
                severity="error",
                path=LITELLM_CONFIG_PATH.as_posix(),
                message="LiteLLM proxy config is missing.",
            )
        ]

    loaded = yaml.safe_load(config_path.read_text(encoding="utf-8"))
    if not isinstance(loaded, dict):
        return set(), [
            ReleaseCheckIssue(
                severity="error",
                path=LITELLM_CONFIG_PATH.as_posix(),
                message="LiteLLM proxy config must be a mapping.",
            )
        ]

    model_list = loaded.get("model_list")
    if not isinstance(model_list, list) or not model_list:
        return set(), [
            ReleaseCheckIssue(
                severity="error",
                path=LITELLM_CONFIG_PATH.as_posix(),
                message="LiteLLM proxy config must define at least one model alias.",
            )
        ]

    aliases: set[str] = set()
    issues: list[ReleaseCheckIssue] = []
    for index, item in enumerate(model_list):
        item_path = f"model_list[{index}]"
        if not isinstance(item, dict):
            issues.append(
                ReleaseCheckIssue(
                    severity="error",
                    path=LITELLM_CONFIG_PATH.as_posix(),
                    message=f"{item_path} must be a mapping.",
                )
            )
            continue
        model_name = item.get("model_name")
        if not isinstance(model_name, str) or not model_name.strip():
            issues.append(
                ReleaseCheckIssue(
                    severity="error",
                    path=LITELLM_CONFIG_PATH.as_posix(),
                    message=f"{item_path}.model_name is required.",
                )
            )
            continue
        model_name = model_name.strip()
        aliases.add(model_name)
        if model_name == "*":
            issues.append(
                ReleaseCheckIssue(
                    severity="error",
                    path=LITELLM_CONFIG_PATH.as_posix(),
                    message="wildcard LiteLLM proxy model aliases are not allowed.",
                )
            )

        params = item.get("litellm_params")
        if not isinstance(params, dict):
            issues.append(
                ReleaseCheckIssue(
                    severity="error",
                    path=LITELLM_CONFIG_PATH.as_posix(),
                    message=f"{item_path}.litellm_params must be a mapping.",
                )
            )
            continue
        provider_model = params.get("model")
        if not _is_env_reference(provider_model):
            issues.append(
                ReleaseCheckIssue(
                    severity="error",
                    path=LITELLM_CONFIG_PATH.as_posix(),
                    message=(
                        f"{item_path}.litellm_params.model must use an "
                        "os.environ reference, not a literal provider model."
                    ),
                )
            )
        provider_key = params.get("api_key")
        if provider_key is not None and not _is_env_reference(provider_key):
            issues.append(
                ReleaseCheckIssue(
                    severity="error",
                    path=LITELLM_CONFIG_PATH.as_posix(),
                    message=(
                        f"{item_path}.litellm_params.api_key must use an "
                        "os.environ reference, not a literal provider key."
                    ),
                )
            )

    for alias in sorted(EXPECTED_LITELLM_SERVICE_ALIASES - aliases):
        issues.append(
            ReleaseCheckIssue(
                severity="error",
                path=LITELLM_CONFIG_PATH.as_posix(),
                message=f"required LiteLLM service alias {alias} is missing.",
            )
        )
    return aliases, issues


def _check_litellm_app_env_examples(
    *,
    repo_root: Path,
    allowed_aliases: set[str],
) -> list[ReleaseCheckIssue]:
    issues: list[ReleaseCheckIssue] = []
    for relative_path in LITELLM_APP_ENV_PATHS:
        path = repo_root / relative_path
        if not path.exists():
            issues.append(
                ReleaseCheckIssue(
                    severity="error",
                    path=relative_path.as_posix(),
                    message="production app env example is missing.",
                )
            )
            continue
        assignments = _env_assignments(path.read_text(encoding="utf-8", errors="ignore"))
        for key in DISALLOWED_APP_PROVIDER_KEYS:
            if key in assignments:
                issues.append(
                    ReleaseCheckIssue(
                        severity="error",
                        path=relative_path.as_posix(),
                        message=f"app service env examples must not set {key}.",
                    )
                )
        if relative_path.name != ".env.prod.example":
            continue
        issues.extend(_require_env_value(assignments, "LLM_PROVIDER_MODE", "litellm", relative_path))
        issues.extend(
            _require_env_value(assignments, "ALLOW_DIRECT_LLM_IN_PROD", "false", relative_path)
        )
        for key in ("LITELLM_BASE_URL", "LITELLM_API_KEY"):
            if not assignments.get(key):
                issues.append(
                    ReleaseCheckIssue(
                        severity="error",
                        path=relative_path.as_posix(),
                        message=f"{key} is required for the production LiteLLM gateway.",
                    )
                )
        for key in APP_LITELLM_ALIAS_ENV_KEYS:
            value = assignments.get(key)
            if not value:
                issues.append(
                    ReleaseCheckIssue(
                        severity="error",
                        path=relative_path.as_posix(),
                        message=f"{key} must be set to a LiteLLM proxy alias.",
                    )
                )
                continue
            if allowed_aliases and value not in allowed_aliases:
                issues.append(
                    ReleaseCheckIssue(
                        severity="error",
                        path=relative_path.as_posix(),
                        message=(
                            f"{key}={value} must reference an alias from "
                            "deploy/litellm/config.yaml."
                        ),
                    )
                )
    return issues


def check_affiliation_copy(
    *,
    repo_root: Path,
    scan_paths: Sequence[str] = DEFAULT_SCAN_PATHS,
) -> list[ReleaseCheckIssue]:
    """Scan runtime copy/code for protected university affiliation claims."""
    issues: list[ReleaseCheckIssue] = []
    for path in _iter_text_files(repo_root, scan_paths):
        rel_path = path.relative_to(repo_root).as_posix()
        text = path.read_text(encoding="utf-8", errors="ignore")
        for line_number, line in enumerate(text.splitlines(), start=1):
            matched = next(
                (term for term in PROTECTED_AFFILIATION_TERMS if term in line),
                None,
            )
            if matched is None:
                continue
            issues.append(
                ReleaseCheckIssue(
                    severity="error",
                    path=f"{rel_path}:{line_number}",
                    message=(
                        f"protected affiliation term '{matched}' found in "
                        "runtime copy/code."
                    ),
                )
            )
    return issues


def check_observability_baseline(*, repo_root: Path) -> list[ReleaseCheckIssue]:
    """Verify required redaction/tracing/request-context anchors exist."""
    issues: list[ReleaseCheckIssue] = []
    for relative_path, snippets in OBSERVABILITY_REQUIRED_SNIPPETS.items():
        path = repo_root / relative_path
        if not path.exists():
            issues.append(
                ReleaseCheckIssue(
                    severity="error",
                    path=relative_path.as_posix(),
                    message="required observability file is missing.",
                )
            )
            continue
        text = path.read_text(encoding="utf-8", errors="ignore")
        for snippet in snippets:
            if snippet not in text:
                issues.append(
                    ReleaseCheckIssue(
                        severity="error",
                        path=relative_path.as_posix(),
                        message=f"required observability guard '{snippet}' is missing.",
                    )
                )
    return issues


def check_rate_limit_release_config(*, repo_root: Path) -> list[ReleaseCheckIssue]:
    """Ensure production env examples opt into app-level rate limiting."""
    prod_env = repo_root / "deploy/envs/.env.prod.example"
    if not prod_env.exists():
        return [
            ReleaseCheckIssue(
                severity="error",
                path="deploy/envs/.env.prod.example",
                message="production env example is missing.",
            )
        ]
    text = prod_env.read_text(encoding="utf-8", errors="ignore")
    issues: list[ReleaseCheckIssue] = []
    required = (
        "RATE_LIMIT_ENABLED=true",
        "RATE_LIMIT_STORE_MODE=valkey",
    )
    for setting in required:
        if setting not in text:
            issues.append(
                ReleaseCheckIssue(
                    severity="error",
                    path="deploy/envs/.env.prod.example",
                    message=(
                        f"{setting} is required for production rate-limit "
                        "release gates."
                    ),
                )
            )
    rate_limit_valkey_url = _env_value(text, "RATE_LIMIT_VALKEY_URL")
    if not rate_limit_valkey_url:
        issues.append(
            ReleaseCheckIssue(
                severity="error",
                path="deploy/envs/.env.prod.example",
                message=(
                    "RATE_LIMIT_VALKEY_URL must be set for production "
                    "rate-limit release gates."
                ),
            )
        )
    return issues


def _dataset_validation_issues(
    *,
    specs: Iterable[object] | None,
) -> list[ReleaseCheckIssue]:
    resolved_specs = list(specs) if specs is not None else list(REGISTRY.values())
    return [
        ReleaseCheckIssue(
            severity=getattr(issue, "severity", "error"),
            path=getattr(issue, "path", "?"),
            message=getattr(issue, "message", str(issue)),
        )
        for issue in validate_specs(resolved_specs)
    ]


def _iter_text_files(repo_root: Path, scan_paths: Sequence[str]) -> Iterable[Path]:
    for relative in scan_paths:
        path = repo_root / relative
        if path.is_file():
            if _is_text_path(path):
                yield path
            continue
        if not path.exists():
            continue
        for child in path.rglob("*"):
            if child.is_file() and _is_text_path(child):
                yield child


def _is_text_path(path: Path) -> bool:
    return path.suffix.lower() in TEXT_SUFFIXES


def _env_value(text: str, key: str) -> str | None:
    prefix = f"{key}="
    for line in text.splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or not stripped.startswith(prefix):
            continue
        return stripped[len(prefix) :].split("#", 1)[0].strip()
    return None


def _env_assignments(text: str) -> dict[str, str]:
    assignments: dict[str, str] = {}
    for line in text.splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "=" not in stripped:
            continue
        key, value = stripped.split("=", 1)
        key = key.strip()
        if not key:
            continue
        assignments[key] = value.split("#", 1)[0].strip().strip("'\"")
    return assignments


def _is_env_reference(value: object) -> bool:
    return isinstance(value, str) and value.startswith("os.environ/")


def _require_env_value(
    assignments: dict[str, str],
    key: str,
    expected: str,
    relative_path: Path,
) -> list[ReleaseCheckIssue]:
    if assignments.get(key) == expected:
        return []
    return [
        ReleaseCheckIssue(
            severity="error",
            path=relative_path.as_posix(),
            message=f"{key}={expected} is required for the production LiteLLM gateway.",
        )
    ]


def _required_string(
    item: dict[object, object],
    key: str,
    item_path: str,
    policy_path: Path,
) -> list[ReleaseCheckIssue]:
    if isinstance(item.get(key), str) and str(item[key]).strip():
        return []
    return [
        ReleaseCheckIssue(
            severity="error",
            path=str(policy_path),
            message=f"{item_path}.{key} is required.",
        )
    ]


def _required_positive_number(
    item: dict[object, object],
    key: str,
    item_path: str,
    policy_path: Path,
) -> list[ReleaseCheckIssue]:
    value = item.get(key)
    if isinstance(value, int | float) and value > 0:
        return []
    return [
        ReleaseCheckIssue(
            severity="error",
            path=str(policy_path),
            message=f"{item_path}.{key} must be a positive number.",
        )
    ]


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[3]
