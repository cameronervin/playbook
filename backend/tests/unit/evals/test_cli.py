from __future__ import annotations

from types import SimpleNamespace

from click.testing import CliRunner

from evals import cli as eval_cli
from evals.core.types import RunResult


def test_run_passes_explicit_max_concurrency(monkeypatch) -> None:
    seen: dict[str, int] = {}

    async def fake_run_spec(spec, *, run_name=None, max_concurrency=5):
        seen["max_concurrency"] = max_concurrency
        return RunResult(
            agent="athlete_chat",
            run_name=run_name or "run",
            mean_scores={},
            passed=True,
            failures=[],
        )

    monkeypatch.setitem(eval_cli.REGISTRY, "athlete_chat", SimpleNamespace())
    monkeypatch.setattr(eval_cli, "_ensure_langfuse", lambda: None)
    monkeypatch.setattr(eval_cli, "_shutdown_langfuse", lambda: None)
    monkeypatch.setattr(eval_cli, "run_spec", fake_run_spec)

    result = CliRunner().invoke(
        eval_cli.cli,
        ["run", "--agent", "athlete_chat", "--max-concurrency", "9"],
    )

    assert result.exit_code == 0
    assert seen == {"max_concurrency": 9}


def test_run_exits_nonzero_when_thresholds_fail(monkeypatch) -> None:
    async def fake_run_spec(spec, *, run_name=None, max_concurrency=5):
        return RunResult(
            agent="athlete_chat",
            run_name=run_name or "run",
            mean_scores={"quality": 0.2},
            passed=False,
            failures=["quality: 0.200 < threshold 0.9"],
        )

    monkeypatch.setitem(eval_cli.REGISTRY, "athlete_chat", SimpleNamespace())
    monkeypatch.setattr(eval_cli, "_ensure_langfuse", lambda: None)
    monkeypatch.setattr(eval_cli, "_shutdown_langfuse", lambda: None)
    monkeypatch.setattr(eval_cli, "run_spec", fake_run_spec)

    result = CliRunner().invoke(eval_cli.cli, ["run", "--agent", "athlete_chat"])

    assert result.exit_code != 0
    assert "quality: 0.200 < threshold 0.9" in result.output


def test_run_reads_max_concurrency_from_env(monkeypatch) -> None:
    seen: dict[str, int] = {}

    async def fake_run_spec(spec, *, run_name=None, max_concurrency=5):
        seen["max_concurrency"] = max_concurrency
        return RunResult(
            agent="athlete_chat",
            run_name=run_name or "run",
            mean_scores={},
            passed=True,
            failures=[],
        )

    monkeypatch.setitem(eval_cli.REGISTRY, "athlete_chat", SimpleNamespace())
    monkeypatch.setattr(eval_cli, "_ensure_langfuse", lambda: None)
    monkeypatch.setattr(eval_cli, "_shutdown_langfuse", lambda: None)
    monkeypatch.setattr(eval_cli, "run_spec", fake_run_spec)

    result = CliRunner().invoke(
        eval_cli.cli,
        ["run", "--agent", "athlete_chat"],
        env={"EVAL_MAX_CONCURRENCY": "7"},
    )

    assert result.exit_code == 0
    assert seen == {"max_concurrency": 7}


def test_run_all_passes_explicit_max_concurrency(monkeypatch) -> None:
    seen: list[int] = []
    spec = SimpleNamespace(dataset_path="exists.yaml")

    async def fake_run_spec(spec, *, run_name=None, max_concurrency=5):
        seen.append(max_concurrency)
        return RunResult(
            agent="athlete_chat",
            run_name=run_name or "run",
            mean_scores={},
            passed=True,
            failures=[],
        )

    monkeypatch.setattr(eval_cli, "REGISTRY", {"athlete_chat": spec})
    monkeypatch.setattr(eval_cli, "_ensure_langfuse", lambda: None)
    monkeypatch.setattr(eval_cli, "_shutdown_langfuse", lambda: None)
    monkeypatch.setattr(eval_cli, "dataset_exists", lambda spec: True)
    monkeypatch.setattr(eval_cli, "run_spec", fake_run_spec)

    result = CliRunner().invoke(
        eval_cli.cli,
        ["run-all", "--max-concurrency", "6"],
    )

    assert result.exit_code == 0
    assert seen == [6]


def test_run_all_strict_fails_on_missing_dataset(monkeypatch) -> None:
    spec = SimpleNamespace(name="missing", dataset_path="missing.yaml")

    monkeypatch.setattr(eval_cli, "REGISTRY", {"missing": spec})
    monkeypatch.setattr(eval_cli, "_ensure_langfuse", lambda: None)
    monkeypatch.setattr(eval_cli, "_shutdown_langfuse", lambda: None)
    monkeypatch.setattr(eval_cli, "dataset_exists", lambda spec: False)

    result = CliRunner().invoke(eval_cli.cli, ["run-all", "--strict"])

    assert result.exit_code != 0
    assert "missing missing: no dataset at missing.yaml" in result.output


def test_run_all_strict_fails_on_failed_spec(monkeypatch) -> None:
    spec = SimpleNamespace(name="athlete_chat", dataset_path="exists.yaml")

    async def fake_run_spec(spec, *, run_name=None, max_concurrency=5):
        return RunResult(
            agent="athlete_chat",
            run_name=run_name or "run",
            mean_scores={"quality": 0.4},
            passed=False,
            failures=["quality failed"],
        )

    monkeypatch.setattr(eval_cli, "REGISTRY", {"athlete_chat": spec})
    monkeypatch.setattr(eval_cli, "_ensure_langfuse", lambda: None)
    monkeypatch.setattr(eval_cli, "_shutdown_langfuse", lambda: None)
    monkeypatch.setattr(eval_cli, "dataset_exists", lambda spec: True)
    monkeypatch.setattr(eval_cli, "run_spec", fake_run_spec)

    result = CliRunner().invoke(eval_cli.cli, ["run-all", "--strict"])

    assert result.exit_code != 0
    assert "athlete_chat failed release thresholds" in result.output


def test_validate_datasets_runs_without_langfuse(monkeypatch) -> None:
    seen: list[str] = []

    class ValidationIssue:
        severity = "error"
        path = "evals/datasets/athlete_chat.yaml"
        message = "missing expected_output"

    def fake_validate_specs(specs):
        seen.extend(spec.name for spec in specs)
        return [ValidationIssue()]

    monkeypatch.setattr(eval_cli, "REGISTRY", {"athlete_chat": SimpleNamespace(name="athlete_chat")})
    monkeypatch.setattr(eval_cli, "validate_specs", fake_validate_specs)

    result = CliRunner().invoke(eval_cli.cli, ["validate-datasets"])

    assert result.exit_code != 0
    assert seen == ["athlete_chat"]
    assert "missing expected_output" in result.output
