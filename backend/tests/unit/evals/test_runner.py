from __future__ import annotations

import asyncio
import sys
import types
from dataclasses import dataclass
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

from evals.core import runner
from evals.core.types import EvalSpec, GraphRun, Score


@dataclass
class FakeDatasetItem:
    id: str
    input: dict[str, str]
    expected_output: str

    def run(self, *args: Any, **kwargs: Any) -> None:
        raise AssertionError("legacy item.run should not be called")


class FakeExperimentResult:
    summary: dict[str, float] = {}


class FakeLangfuseClient:
    def __init__(self, items: list[FakeDatasetItem]) -> None:
        self.dataset = SimpleNamespace(items=items)
        self.run_experiment_calls: list[dict[str, Any]] = []
        self.evaluations_by_item: dict[str, list[Any]] = {}
        self.current_item_id: str | None = None
        self.flushed = False

    def get_dataset(self, name: str) -> Any:
        return self.dataset

    def get_current_trace_id(self) -> str:
        return f"trace-{self.current_item_id}"

    def create_score(self, *args: Any, **kwargs: Any) -> None:
        raise AssertionError("manual create_score should not be called")

    def flush(self) -> None:
        self.flushed = True

    def run_experiment(
        self,
        *,
        name: str,
        dataset: Any,
        task: Any,
        evaluators: list[Any],
        max_concurrency: int,
        description: str,
    ) -> FakeExperimentResult:
        self.run_experiment_calls.append(
            {
                "name": name,
                "dataset": dataset,
                "task": task,
                "evaluators": evaluators,
                "max_concurrency": max_concurrency,
                "description": description,
            }
        )

        async def _run_items() -> None:
            semaphore = asyncio.Semaphore(max_concurrency)

            async def _run_one(item: FakeDatasetItem) -> None:
                async with semaphore:
                    self.current_item_id = item.id
                    try:
                        output = await task(item=item)
                    except Exception:  # noqa: BLE001 - fake Langfuse isolates item failures.
                        return
                    self.evaluations_by_item[item.id] = evaluators[0](
                        input=item.input,
                        output=output,
                        expected_output=item.expected_output,
                    )

            await asyncio.gather(*(_run_one(item) for item in dataset.items))

        asyncio.run(_run_items())
        return FakeExperimentResult()


class FakeJudge:
    async def score(
        self,
        *,
        run: GraphRun,
        rubric: Any,
        expected_output: object,
    ) -> list[Score]:
        return [
            Score(
                name=f"{rubric.name}_score",
                value=1.0,
                comment=f"judged {run.output} against {expected_output}",
            )
        ]


def _install_fake_langfuse(monkeypatch: pytest.MonkeyPatch, client: FakeLangfuseClient) -> None:
    class Evaluation:
        def __init__(
            self,
            *,
            name: str,
            value: float | str | bool,
            data_type: str = "NUMERIC",
            comment: str | None = None,
        ) -> None:
            self.name = name
            self.value = value
            self.data_type = data_type
            self.comment = comment

    module = types.SimpleNamespace(
        Evaluation=Evaluation,
        get_client=lambda: client,
    )
    monkeypatch.setitem(sys.modules, "langfuse", module)


def _patch_runner_io(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setattr(runner, "sync_dataset_to_langfuse", lambda *args, **kwargs: 0)
    monkeypatch.setattr(
        runner,
        "load_rubric",
        lambda path: SimpleNamespace(name=Path(path).stem),
    )
    monkeypatch.setattr(
        runner,
        "write_run_result",
        lambda result: (tmp_path / "result.json", tmp_path / "result.md"),
    )


@pytest.mark.asyncio
async def test_run_spec_uses_langfuse_experiment_runner(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    items = [
        FakeDatasetItem("one", {"question": "Q1"}, "A1"),
        FakeDatasetItem("two", {"question": "Q2"}, "A2"),
    ]
    client = FakeLangfuseClient(items)
    _install_fake_langfuse(monkeypatch, client)
    _patch_runner_io(monkeypatch, tmp_path)

    async def adapter(*, item: FakeDatasetItem) -> GraphRun:
        return GraphRun(input=item.input, output=f"answer-{item.id}")

    spec = EvalSpec(
        name="example",
        dataset_path="evals/datasets/example.yaml",
        adapter=adapter,
        rubrics=["rubrics/quality.yaml"],
        judge=FakeJudge(),
        thresholds={"quality_score": 0.5},
    )

    result = await runner.run_spec(spec, run_name="experiment-run", max_concurrency=5)

    assert result.passed is True
    assert client.run_experiment_calls[0]["max_concurrency"] == 5
    assert client.run_experiment_calls[0]["dataset"] is client.dataset
    assert client.flushed is True
    assert result.mean_scores == {"quality_score": 1.0}
    assert sorted(client.evaluations_by_item) == ["one", "two"]
    assert client.evaluations_by_item["one"][0].name == "quality_score"


@pytest.mark.asyncio
async def test_run_spec_records_agent_failures_without_blocking_other_items(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    items = [
        FakeDatasetItem("good", {"question": "Q1"}, "A1"),
        FakeDatasetItem("bad", {"question": "Q2"}, "A2"),
    ]
    client = FakeLangfuseClient(items)
    _install_fake_langfuse(monkeypatch, client)
    _patch_runner_io(monkeypatch, tmp_path)

    async def adapter(*, item: FakeDatasetItem) -> GraphRun:
        if item.id == "bad":
            raise RuntimeError("agent exploded")
        return GraphRun(input=item.input, output=f"answer-{item.id}")

    spec = EvalSpec(
        name="example",
        dataset_path="evals/datasets/example.yaml",
        adapter=adapter,
        rubrics=["rubrics/quality.yaml"],
        judge=FakeJudge(),
        thresholds={"quality_score": 0.5},
    )

    result = await runner.run_spec(spec, run_name="partial-run", max_concurrency=5)

    assert result.passed is True
    assert result.mean_scores == {"quality_score": 1.0}
    assert result.errors == ["agent run on item bad: agent exploded"]
    assert sorted(client.evaluations_by_item) == ["good"]
