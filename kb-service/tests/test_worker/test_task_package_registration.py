from __future__ import annotations

import importlib

from app.workers import tasks


def test_worker_tasks_package_exports_registered_tasks() -> None:
    expected_task_names = {
        "parse_task": "app.workers.tasks.parse_task",
        "chunk_task": "app.workers.tasks.chunk_task",
        "summarize_task": "app.workers.tasks.summarize_task",
        "embed_task": "app.workers.tasks.embed_task",
        "embed_batch_task": "app.workers.tasks.embed_batch_task",
        "load_vector_task": "app.workers.tasks.load_vector_task",
        "notify_status_task": "app.workers.tasks.notify_status_task",
        "reconcile_stuck_embeds": "app.workers.tasks.reconcile_stuck_embeds",
    }

    assert hasattr(tasks, "__path__")

    for module_name in (
        "ingest",
        "summary",
        "embedding",
        "finalize",
        "notify",
        "progress",
        "staging",
        "text_validation",
        "watchdog",
    ):
        importlib.import_module(f"app.workers.tasks.{module_name}")

    for export_name, task_name in expected_task_names.items():
        assert getattr(tasks, export_name).name == task_name
