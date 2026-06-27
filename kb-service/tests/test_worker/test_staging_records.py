from __future__ import annotations

import json

import app.workers.tasks.staging as staging
from app.core.config import settings


class _FakeBody:
    def __init__(self, payload: bytes) -> None:
        self._payload = payload
        self.closed = False

    def iter_lines(self):
        return iter(self._payload.splitlines())

    def close(self) -> None:
        self.closed = True


class _FakeS3Client:
    def __init__(self) -> None:
        self.uploaded: bytes | None = None

    def upload_fileobj(self, fileobj, *, Bucket: str, Key: str, ExtraArgs: dict) -> None:
        self.uploaded = fileobj.read()

    def get_object(self, *, Bucket: str, Key: str) -> dict:
        assert self.uploaded is not None
        return {"Body": _FakeBody(self.uploaded)}


def test_page_staging_round_trips_segment_records(monkeypatch) -> None:
    client = _FakeS3Client()
    monkeypatch.setattr(settings, "S3_BUCKET_NAME", "bucket")

    def fake_build_s3_client() -> _FakeS3Client:
        return client

    monkeypatch.setattr(
        "app.infrastructure.io.s3_client.build_s3_client",
        fake_build_s3_client,
    )

    records = [
        {
            "text": "Private contract text",
            "source_locator": {"type": "page", "page_number": 2},
        }
    ]

    key = staging._save_pages_to_s3("doc-1", records)
    loaded = list(staging._iter_pages_from_s3("doc-1"))

    assert key == "kb/staging/doc-1/pages.ndjson"
    assert loaded == records
    assert json.loads(client.uploaded.decode("utf-8").strip()) == records[0]
