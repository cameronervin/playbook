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
            agent="example",
            run_name=run_name or "run",
            mean_scores={},
            passed=True,
            failures=[],
        )

    monkeypatch.setitem(eval_cli.REGISTRY, "example", SimpleNamespace())
    monkeypatch.setattr(eval_cli, "_ensure_langfuse", lambda: None)
    monkeypatch.setattr(eval_cli, "_shutdown_langfuse", lambda: None)
    monkeypatch.setattr(eval_cli, "run_spec", fake_run_spec)

    result = CliRunner().invoke(
        eval_cli.cli,
        ["run", "--agent", "example", "--max-concurrency", "9"],
    )

    assert result.exit_code == 0
    assert seen == {"max_concurrency": 9}


def test_run_reads_max_concurrency_from_env(monkeypatch) -> None:
    seen: dict[str, int] = {}

    async def fake_run_spec(spec, *, run_name=None, max_concurrency=5):
        seen["max_concurrency"] = max_concurrency
        return RunResult(
            agent="example",
            run_name=run_name or "run",
            mean_scores={},
            passed=True,
            failures=[],
        )

    monkeypatch.setitem(eval_cli.REGISTRY, "example", SimpleNamespace())
    monkeypatch.setattr(eval_cli, "_ensure_langfuse", lambda: None)
    monkeypatch.setattr(eval_cli, "_shutdown_langfuse", lambda: None)
    monkeypatch.setattr(eval_cli, "run_spec", fake_run_spec)

    result = CliRunner().invoke(
        eval_cli.cli,
        ["run", "--agent", "example"],
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
            agent="example",
            run_name=run_name or "run",
            mean_scores={},
            passed=True,
            failures=[],
        )

    monkeypatch.setattr(eval_cli, "REGISTRY", {"example": spec})
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
