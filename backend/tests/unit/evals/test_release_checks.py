from __future__ import annotations

from pathlib import Path

import yaml
from click.testing import CliRunner

from evals import cli as eval_cli
from evals.core.release_checks import (
    check_affiliation_copy,
    check_litellm_gateway_controls,
    check_litellm_virtual_key_policy,
    check_production_coverage_policy,
    check_rate_limit_release_config,
)

_GATEWAY_ALIASES = [
    "playbook-chat",
    "playbook-fast",
    "playbook-embed",
    "playbook-ocr",
    "playbook-rerank",
]


def _write_gateway_fixture(
    repo_root: Path,
    *,
    config_model_names: list[str] | None = None,
    policy_models: list[str] | None = None,
    prod_env_extra: str = "",
) -> None:
    config_dir = repo_root / "deploy" / "litellm"
    config_dir.mkdir(parents=True)
    config_dir.joinpath("config.yaml").write_text(
        yaml.safe_dump(
            {
                "model_list": [
                    {
                        "model_name": model_name,
                        "litellm_params": {
                            "model": f"os.environ/{model_name.upper().replace('-', '_')}_MODEL",
                            "api_key": "os.environ/OPENAI_API_KEY",
                        },
                    }
                    for model_name in (config_model_names or _GATEWAY_ALIASES)
                ]
            }
        ),
        encoding="utf-8",
    )

    policy_dir = repo_root / "backend" / "evals" / "release"
    policy_dir.mkdir(parents=True)
    policy_dir.joinpath("litellm_virtual_key_policy.yaml").write_text(
        yaml.safe_dump(
            {
                "virtual_keys": [
                    {
                        "name": "backend-api",
                        "allowed_models": policy_models or _GATEWAY_ALIASES,
                        "max_budget": 100,
                        "budget_duration": "1d",
                        "rpm_limit": 60,
                    }
                ]
            }
        ),
        encoding="utf-8",
    )

    env_dir = repo_root / "deploy" / "envs"
    env_dir.mkdir(parents=True)
    env_dir.joinpath(".env.prod.example").write_text(
        "\n".join(
            [
                "LLM_PROVIDER_MODE=litellm",
                "ALLOW_DIRECT_LLM_IN_PROD=false",
                "LLM_CHAT_MODEL=playbook-chat",
                "LITELLM_BASE_URL=http://litellm:4000",
                "LITELLM_API_KEY=${LITELLM_API_KEY}",
                "LITELLM_EMBED_MODEL=playbook-embed",
                "LITELLM_SUMMARY_MODEL=playbook-fast",
                "LITELLM_RERANK_MODEL=playbook-rerank",
                prod_env_extra,
            ]
        ),
        encoding="utf-8",
    )
    env_dir.joinpath(".env.backend.prod.example").write_text(
        "SENTRY_DSN=${BACKEND_SENTRY_DSN}\n",
        encoding="utf-8",
    )
    env_dir.joinpath(".env.kb-service.prod.example").write_text(
        "SENTRY_DSN=${KB_SERVICE_SENTRY_DSN}\n",
        encoding="utf-8",
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


def test_litellm_policy_documents_scoped_backend_kb_and_eval_keys() -> None:
    policy_path = (
        Path(__file__).resolve().parents[3]
        / "evals"
        / "release"
        / "litellm_virtual_key_policy.yaml"
    )
    loaded = yaml.safe_load(policy_path.read_text(encoding="utf-8"))

    policies = {
        item["name"]: set(item["allowed_models"])
        for item in loaded["virtual_keys"]
    }

    assert policies == {
        "backend": {"playbook-chat", "playbook-fast"},
        "kb-service": {
            "playbook-embed",
            "playbook-fast",
            "playbook-rerank",
            "playbook-ocr",
        },
        "eval": {"playbook-chat", "playbook-fast", "playbook-embed"},
    }


def test_litellm_gateway_controls_require_policy_models_in_proxy_config(
    tmp_path: Path,
) -> None:
    _write_gateway_fixture(
        tmp_path,
        policy_models=[*_GATEWAY_ALIASES, "raw-provider-model"],
    )

    issues = check_litellm_gateway_controls(repo_root=tmp_path)

    assert any(
        "raw-provider-model is not defined in deploy/litellm/config.yaml"
        in issue.message
        for issue in issues
    )


def test_litellm_gateway_controls_reject_wildcard_proxy_models(
    tmp_path: Path,
) -> None:
    _write_gateway_fixture(tmp_path, config_model_names=[*_GATEWAY_ALIASES, "*"])

    issues = check_litellm_gateway_controls(repo_root=tmp_path)

    assert any("wildcard LiteLLM proxy model aliases are not allowed" in issue.message for issue in issues)


def test_litellm_gateway_controls_reject_provider_keys_in_app_env_examples(
    tmp_path: Path,
) -> None:
    _write_gateway_fixture(tmp_path, prod_env_extra="OPENAI_API_KEY=${OPENAI_API_KEY}")

    issues = check_litellm_gateway_controls(repo_root=tmp_path)

    assert any("must not set OPENAI_API_KEY" in issue.message for issue in issues)


def test_litellm_gateway_controls_accept_alias_only_prod_config(tmp_path: Path) -> None:
    _write_gateway_fixture(tmp_path)

    assert check_litellm_gateway_controls(repo_root=tmp_path) == []


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


def test_production_coverage_policy_accepts_required_surface_evidence(
    tmp_path: Path,
) -> None:
    manifest_path = tmp_path / "backstage" / "production" / "coverage-policy.yaml"
    manifest_path.parent.mkdir(parents=True)
    manifest_path.write_text(
        yaml.safe_dump(
            {
                "version": 1,
                "required_surfaces": ["auth"],
                "surfaces": {
                    "auth": {
                        "description": "Authentication tests exist.",
                        "evidence": {
                            "tests": ["backend/tests/integration/test_auth_routes.py"],
                            "docs": ["backstage/production/coverage-policy.md"],
                        },
                    }
                },
            }
        ),
        encoding="utf-8",
    )
    tmp_path.joinpath("backend/tests/integration").mkdir(parents=True)
    tmp_path.joinpath("backend/tests/integration/test_auth_routes.py").write_text(
        "def test_auth() -> None:\n    assert True\n",
        encoding="utf-8",
    )
    tmp_path.joinpath("backstage/production/coverage-policy.md").write_text(
        "# Coverage Policy\n",
        encoding="utf-8",
    )

    assert check_production_coverage_policy(repo_root=tmp_path) == []


def test_production_coverage_policy_requires_all_required_surfaces(
    tmp_path: Path,
) -> None:
    manifest_path = tmp_path / "backstage" / "production" / "coverage-policy.yaml"
    manifest_path.parent.mkdir(parents=True)
    manifest_path.write_text(
        yaml.safe_dump(
            {
                "version": 1,
                "required_surfaces": ["auth", "privacy"],
                "surfaces": {
                    "auth": {
                        "evidence": {
                            "tests": ["backend/tests/integration/test_auth_routes.py"],
                        }
                    }
                },
            }
        ),
        encoding="utf-8",
    )
    tmp_path.joinpath("backend/tests/integration").mkdir(parents=True)
    tmp_path.joinpath("backend/tests/integration/test_auth_routes.py").write_text(
        "def test_auth() -> None:\n    assert True\n",
        encoding="utf-8",
    )

    issues = check_production_coverage_policy(repo_root=tmp_path)

    assert any("required coverage surface privacy is missing" in issue.message for issue in issues)


def test_production_coverage_policy_requires_referenced_files(
    tmp_path: Path,
) -> None:
    manifest_path = tmp_path / "backstage" / "production" / "coverage-policy.yaml"
    manifest_path.parent.mkdir(parents=True)
    manifest_path.write_text(
        yaml.safe_dump(
            {
                "version": 1,
                "required_surfaces": ["uploads"],
                "surfaces": {
                    "uploads": {
                        "evidence": {
                            "tests": [
                                "backend/tests/unit/test_direct_upload_workflows.py",
                            ],
                            "docs": ["backstage/production/missing-doc.md"],
                        }
                    }
                },
            }
        ),
        encoding="utf-8",
    )

    issues = check_production_coverage_policy(repo_root=tmp_path)

    assert any(
        "referenced test backend/tests/unit/test_direct_upload_workflows.py is missing"
        in issue.message
        for issue in issues
    )
    assert any(
        "referenced doc backstage/production/missing-doc.md is missing" in issue.message
        for issue in issues
    )


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
