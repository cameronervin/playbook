from __future__ import annotations

import asyncio
from uuid import uuid4

import pytest

import app.workers.tasks as tasks
from app.services.ingestion.pipeline_dispatcher import IngestionPipelineDispatcher


def test_dispatch_pipeline_preserves_task_order_and_persists_result_id(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    order: list[str] = []
    persisted: list[tuple[object, str]] = []

    class FakeSignature:
        def __init__(self, name: str) -> None:
            self.name = name

        def __or__(self, other: "FakeSignature") -> "FakePipeline":
            return FakePipeline([self, other])

    class FakePipeline:
        def __init__(self, items: list[FakeSignature]) -> None:
            self.items = items

        def __or__(self, other: FakeSignature) -> "FakePipeline":
            self.items.append(other)
            return self

        def apply_async(self):
            order.extend(item.name for item in self.items)
            return type("Result", (), {"id": "pipeline-task"})()

    class FakeTask:
        def __init__(self, name: str) -> None:
            self.name = name

        def s(self, *args, **kwargs) -> FakeSignature:
            return FakeSignature(self.name)

    class FakeLogRepo:
        async def set_root_task_id(self, document_id, root_task_id):
            persisted.append((document_id, root_task_id))
            return None

    monkeypatch.setattr(tasks, "parse_task", FakeTask("parse"), raising=False)
    monkeypatch.setattr(tasks, "chunk_task", FakeTask("chunk"), raising=False)
    monkeypatch.setattr(tasks, "summarize_task", FakeTask("summarize"), raising=False)
    monkeypatch.setattr(tasks, "embed_task", FakeTask("embed"), raising=False)

    document_id = uuid4()
    dispatcher = IngestionPipelineDispatcher(FakeLogRepo())

    task_id = asyncio.run(
        dispatcher.dispatch(
            document_id,
            type("Config", (), {"id": uuid4()})(),
            "kb/originals/doc.pdf",
            "doc.pdf",
            {"source_type": "admin_upload"},
        )
    )

    assert task_id == "pipeline-task"
    assert order == ["parse", "chunk", "summarize", "embed"]
    assert persisted == [(document_id, "pipeline-task")]
