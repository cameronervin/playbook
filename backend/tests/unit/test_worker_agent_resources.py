from __future__ import annotations

import app.workers.app as worker_app


async def test_worker_checkpointer_is_reused_and_cleaned_up(
    test_settings,
    monkeypatch,
) -> None:
    calls: dict[str, int] = {
        "pool": 0,
        "checkpointer": 0,
        "cleanup": 0,
    }
    pool = object()
    checkpointer = object()

    async def fake_create_pool(_settings):
        calls["pool"] += 1
        return pool

    async def fake_create_checkpointer(_pool):
        calls["checkpointer"] += 1
        return checkpointer

    async def fake_cleanup_pool(_pool):
        calls["cleanup"] += 1

    monkeypatch.setattr(worker_app, "_worker_checkpointer_pool", None)
    monkeypatch.setattr(worker_app, "_worker_checkpointer", None)
    monkeypatch.setattr(worker_app, "create_checkpointer_pool", fake_create_pool)
    monkeypatch.setattr(worker_app, "create_checkpointer", fake_create_checkpointer)
    monkeypatch.setattr(worker_app, "cleanup_checkpointer_pool", fake_cleanup_pool)

    first = await worker_app.get_worker_checkpointer(test_settings)
    second = await worker_app.get_worker_checkpointer(test_settings)
    await worker_app.cleanup_worker_checkpointer()

    assert first is checkpointer
    assert second is checkpointer
    assert calls == {"pool": 1, "checkpointer": 1, "cleanup": 1}
    assert worker_app._worker_checkpointer is None
    assert worker_app._worker_checkpointer_pool is None
