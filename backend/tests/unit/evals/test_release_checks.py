from __future__ import annotations

from pathlib import Path

import yaml
from click.testing import CliRunner

from evals import cli as eval_cli
from evals.core.release_checks import (
    check_affiliation_copy,
    check_litellm_virtual_key_policy,
    check_rate_limit_release_config,
)


def test_affiliation_copy_check_flags_protected_university_claim(
    tmp_path: Path,
) -> None:
    runtime_copy = tmp_path / "frontend" / "src" / "page.tsx"
    runtime_copy.parent.mkdir(parents=True)
    runtime_copy.write_text(
        "export const copy = 'The official University of Texas athletics assistant'",
        encoding="utf-8",
    )

    issues = check_affiliation_copy(
        repo_root=tmp_path,
        scan_paths=("frontend/src",),
    )

    assert len(issues) == 1
    assert "protected affiliation term" in issues[0].message
    assert "frontend/src/page.tsx" in issues[0].path


def test_litellm_policy_requires_budget_and_rate_fields(tmp_path: Path) -> None:
    policy_path = tmp_path / "litellm_virtual_key_policy.yaml"
    policy_path.write_text(
        yaml.safe_dump(
            {
                "virtual_keys": [
                    {
                        "name": "backend",
                        "allowed_models": ["playbook-chat"],
                        "max_budget": 100,
                    }
                ]
            }
        ),
        encoding="utf-8",
    )

    issues = check_litellm_virtual_key_policy(policy_path)

    assert {issue.message for issue in issues} >= {
        "virtual_keys[0].budget_duration is required.",
        "virtual_keys[0].rpm_limit must be a positive number.",
    }


def test_rate_limit_release_config_accepts_internal_valkey_url(tmp_path: Path) -> None:
    env_path = tmp_path / "deploy" / "envs" / ".env.prod.example"
    env_path.parent.mkdir(parents=True)
    env_path.write_text(
        "\n".join(
            [
                "RATE_LIMIT_ENABLED=true",
                "RATE_LIMIT_STORE_MODE=valkey",
                "RATE_LIMIT_VALKEY_URL=redis://valkey:6379/3",
            ]
        ),
        encoding="utf-8",
    )

    assert check_rate_limit_release_config(repo_root=tmp_path) == []


def test_rate_limit_release_config_requires_url_value(tmp_path: Path) -> None:
    env_path = tmp_path / "deploy" / "envs" / ".env.prod.example"
    env_path.parent.mkdir(parents=True)
    env_path.write_text(
        "\n".join(
            [
                "RATE_LIMIT_ENABLED=true",
                "RATE_LIMIT_STORE_MODE=valkey",
                "RATE_LIMIT_VALKEY_URL=",
            ]
        ),
        encoding="utf-8",
    )

    issues = check_rate_limit_release_config(repo_root=tmp_path)

    assert issues
    assert "RATE_LIMIT_VALKEY_URL must be set" in issues[0].message


def test_release_checks_cli_reports_failures_without_langfuse(monkeypatch) -> None:
    class Result:
        passed = False
        issues = [
            type(
                "Issue",
                (),
                {
                    "severity": "error",
                    "path": "deploy/litellm/config.yaml",
                    "message": "missing budget policy",
                },
            )()
        ]

        def summary(self) -> str:
            return "FAIL release checks (1 issue)"

    monkeypatch.setattr(eval_cli, "run_release_checks", lambda: Result())

    result = CliRunner().invoke(eval_cli.cli, ["release-checks"])

    assert result.exit_code != 0
    assert "FAIL release checks" in result.output
    assert "missing budget policy" in result.output
