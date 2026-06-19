from __future__ import annotations

from typing import Any

import pytest

from app.services import upload_reconciliation_service as reconciliation_module
from app.services.upload_reconciliation_service import (
    UploadRequestReconciliationService,
    _ProcessOutcome,
)


class FakeUploadRequestRepository:
    async def list_expired_pending_requests(
        self,
        **_: object,
    ) -> list[object]:
        return []

    async def next_pending_expiration_at(self) -> None:
        return None


class FakeCountRepository:
    async def count_by_status(self, **_: object) -> int:
        return 0


class FakeOutboxRepository:
    async def count_due(self, **_: object) -> int:
        return 0


class RecordingLogger:
    def __init__(self) -> None:
        self.debug_calls: list[tuple[str, dict[str, Any]]] = []
        self.info_calls: list[tuple[str, dict[str, Any]]] = []

    def debug(self, event: str, **context: Any) -> None:
        self.debug_calls.append((event, context))

    def info(self, event: str, **context: Any) -> None:
        self.info_calls.append((event, context))


@pytest.mark.asyncio
async def test_zero_work_reconciliation_completion_logs_at_debug(
    monkeypatch,
) -> None:
    recorder = RecordingLogger()
    monkeypatch.setattr(reconciliation_module, "logger", recorder)

    await UploadRequestReconciliationService(
        session=object(),  # type: ignore[arg-type]
        storage=object(),  # type: ignore[arg-type]
        upload_request_repo=FakeUploadRequestRepository(),  # type: ignore[arg-type]
        document_repo=FakeCountRepository(),  # type: ignore[arg-type]
        file_repo=FakeCountRepository(),  # type: ignore[arg-type]
        outbox_repo=FakeOutboxRepository(),  # type: ignore[arg-type]
    ).reconcile_expired(limit=10)

    assert recorder.info_calls == []
    assert recorder.debug_calls[0][0] == "upload_request_reconciliation_completed"
    assert recorder.debug_calls[0][1]["processed"] == 0


@pytest.mark.asyncio
async def test_reconciliation_completion_logs_at_info_when_work_occurs(
    monkeypatch,
) -> None:
    recorder = RecordingLogger()
    monkeypatch.setattr(reconciliation_module, "logger", recorder)
    outcomes = iter(
        [
            _ProcessOutcome(expired=True, cleanup_status="missing"),
            None,
        ]
    )
    service = UploadRequestReconciliationService(
        session=object(),  # type: ignore[arg-type]
        storage=object(),  # type: ignore[arg-type]
        upload_request_repo=FakeUploadRequestRepository(),  # type: ignore[arg-type]
        document_repo=FakeCountRepository(),  # type: ignore[arg-type]
        file_repo=FakeCountRepository(),  # type: ignore[arg-type]
        outbox_repo=FakeOutboxRepository(),  # type: ignore[arg-type]
    )

    async def fake_process_next_expired_request() -> _ProcessOutcome | None:
        return next(outcomes)

    monkeypatch.setattr(
        service,
        "_process_next_expired_request",
        fake_process_next_expired_request,
    )

    await service.reconcile_expired(limit=10)

    assert recorder.debug_calls == []
    assert recorder.info_calls[0][0] == "upload_request_reconciliation_completed"
    assert recorder.info_calls[0][1]["processed"] == 1
