from __future__ import annotations

import sys
from types import SimpleNamespace
from typing import Any

from evals.core import sync


class _FlakyLangfuseClient:
    def __init__(self) -> None:
        self.dataset_names: list[str] = []
        self.item_attempts = 0
        self.items: list[dict[str, Any]] = []
        self.flushed = False

    def create_dataset(self, *, name: str) -> None:
        self.dataset_names.append(name)

    def create_dataset_item(self, **kwargs: Any) -> None:
        self.item_attempts += 1
        if self.item_attempts == 1:
            raise TimeoutError("langfuse read timed out")
        self.items.append(kwargs)

    def flush(self) -> None:
        self.flushed = True


def test_sync_dataset_retries_transient_langfuse_item_timeout(
    tmp_path,
    monkeypatch,
) -> None:
    dataset_path = tmp_path / "dataset.yaml"
    dataset_path.write_text(
        """
- input:
    question: What is the NIL disclosure timing?
  expected_output:
    answer_type: grounded_answer
    expected_source_ids:
      - src:nil-policy#chunk-1
  metadata:
    fixture: retry-test
""",
        encoding="utf-8",
    )
    fake_client = _FlakyLangfuseClient()

    monkeypatch.setitem(
        sys.modules,
        "langfuse",
        SimpleNamespace(get_client=lambda: fake_client),
    )
    monkeypatch.setattr(sync.time, "sleep", lambda _: None)

    count = sync.sync_dataset_to_langfuse(str(dataset_path), "athlete_chat")

    assert count == 1
    assert fake_client.dataset_names == ["athlete_chat"]
    assert fake_client.item_attempts == 2
    assert len(fake_client.items) == 1
    assert fake_client.items[0]["dataset_name"] == "athlete_chat"
    assert fake_client.items[0]["input"] == {
        "question": "What is the NIL disclosure timing?"
    }
    assert fake_client.flushed is True
