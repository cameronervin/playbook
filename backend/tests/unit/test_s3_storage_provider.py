"""Tests for the S3-compatible storage provider."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

import pytest
from botocore.exceptions import ClientError

from app.core.config import Settings
from app.core.exceptions import StorageError
from app.infrastructure.storage.s3_client import S3StorageProvider


class FakeS3Client:
    """Small boto3 S3 client fake for storage unit tests."""

    def __init__(self) -> None:
        self.presigned_post_calls: list[dict[str, Any]] = []
        self.head_response: dict[str, Any] | Exception = {}

    def head_bucket(self, Bucket: str) -> None:
        return None

    def generate_presigned_post(
        self,
        Bucket: str,
        Key: str,
        Fields: dict[str, str],
        Conditions: list[Any],
        ExpiresIn: int,
    ) -> dict[str, Any]:
        self.presigned_post_calls.append(
            {
                "Bucket": Bucket,
                "Key": Key,
                "Fields": Fields,
                "Conditions": Conditions,
                "ExpiresIn": ExpiresIn,
            }
        )
        return {
            "url": "http://minio:9000/playbook-bucket",
            "fields": {
                "key": Key,
                "Content-Type": Fields["Content-Type"],
                "policy": "encoded-policy",
                "x-amz-signature": "signature",
            },
        }

    def generate_presigned_url(
        self,
        ClientMethod: str,
        Params: dict[str, str],
        ExpiresIn: int,
    ) -> str:
        return f"http://minio:9000/{Params['Bucket']}/{Params['Key']}?signature=secret"

    def head_object(self, Bucket: str, Key: str) -> dict[str, Any]:
        if isinstance(self.head_response, Exception):
            raise self.head_response
        return self.head_response


def _settings(**overrides: object) -> Settings:
    values = {
        "DATABASE_URL": "postgresql+asyncpg://app:pass@localhost:5432/playbook",
        "SECRET_KEY": "not-the-default-secret",
        "LLM_PROVIDER_MODE": "direct",
        "LLM_DIRECT_PROVIDER": "anthropic",
        "ANTHROPIC_API_KEY": "anthropic-key",
        "S3_ENDPOINT_URL": "http://minio:9000",
        "S3_PUBLIC_ENDPOINT_URL": "http://localhost:9000",
        "S3_BUCKET_NAME": "playbook-bucket",
        "S3_ACCESS_KEY_ID": "access-key",
        "S3_SECRET_ACCESS_KEY": "secret-key",
        "S3_PRESIGNED_URL_EXPIRY": 900,
    }
    values.update(overrides)
    return Settings(_env_file=None, **values)


def _provider(monkeypatch: pytest.MonkeyPatch, client: FakeS3Client) -> S3StorageProvider:
    monkeypatch.setattr(
        "app.infrastructure.storage.s3_client.boto3.client",
        lambda **_: client,
    )
    return S3StorageProvider(_settings())


@pytest.mark.asyncio
async def test_create_presigned_post_constrains_browser_upload_policy(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    client = FakeS3Client()
    provider = _provider(monkeypatch, client)

    result = await provider.create_presigned_post(
        key="conversation-files/originals/file.pdf",
        content_type="application/pdf",
        max_size_bytes=1024,
        expires_in=600,
    )

    assert result.url == "http://localhost:9000/playbook-bucket"
    assert result.fields["key"] == "conversation-files/originals/file.pdf"
    assert result.fields["Content-Type"] == "application/pdf"
    assert result.expires_at.tzinfo is UTC
    assert result.expires_at > datetime.now(UTC)
    assert client.presigned_post_calls == [
        {
            "Bucket": "playbook-bucket",
            "Key": "conversation-files/originals/file.pdf",
            "Fields": {
                "key": "conversation-files/originals/file.pdf",
                "Content-Type": "application/pdf",
            },
            "Conditions": [
                {"key": "conversation-files/originals/file.pdf"},
                {"Content-Type": "application/pdf"},
                ["content-length-range", 1, 1024],
            ],
            "ExpiresIn": 600,
        }
    ]


@pytest.mark.asyncio
async def test_get_presigned_url_keeps_internal_endpoint_for_backend_flows(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    provider = _provider(monkeypatch, FakeS3Client())

    result = await provider.get_presigned_url("kb/originals/document.pdf")

    assert result.startswith("http://minio:9000/")


@pytest.mark.asyncio
async def test_head_object_maps_safe_metadata(monkeypatch: pytest.MonkeyPatch) -> None:
    client = FakeS3Client()
    client.head_response = {
        "ContentLength": 123,
        "ContentType": "application/pdf",
        "ETag": '"etag-value"',
        "ChecksumCRC32": "crc32",
        "ChecksumCRC32C": "crc32c",
        "ChecksumSHA1": "sha1",
        "ChecksumSHA256": "sha256",
        "Metadata": {"uploaded-by": "playbook"},
    }
    provider = _provider(monkeypatch, client)

    result = await provider.get_object_metadata("kb/originals/document.pdf")

    assert result is not None
    assert result.key == "kb/originals/document.pdf"
    assert result.content_length == 123
    assert result.content_type == "application/pdf"
    assert result.etag == '"etag-value"'
    assert result.checksum_crc32 == "crc32"
    assert result.checksum_crc32c == "crc32c"
    assert result.checksum_sha1 == "sha1"
    assert result.checksum_sha256 == "sha256"
    assert result.user_metadata == {"uploaded-by": "playbook"}


@pytest.mark.asyncio
@pytest.mark.parametrize("error_code", ["404", "NoSuchKey", "NotFound"])
async def test_head_object_returns_none_for_missing_object(
    monkeypatch: pytest.MonkeyPatch,
    error_code: str,
) -> None:
    client = FakeS3Client()
    client.head_response = ClientError(
        {"Error": {"Code": error_code, "Message": "missing"}},
        "HeadObject",
    )
    provider = _provider(monkeypatch, client)

    assert await provider.get_object_metadata("missing.pdf") is None


@pytest.mark.asyncio
async def test_head_object_raises_sanitized_storage_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    client = FakeS3Client()
    client.head_response = ClientError(
        {
            "Error": {
                "Code": "AccessDenied",
                "Message": (
                    "denied for http://minio:9000/file.pdf?"
                    "X-Amz-Signature=secret-signature"
                ),
            }
        },
        "HeadObject",
    )
    provider = _provider(monkeypatch, client)

    with pytest.raises(StorageError) as exc_info:
        await provider.get_object_metadata("private.pdf")

    message = str(exc_info.value)
    assert "secret-signature" not in message
    assert "X-Amz-Signature" not in message
    assert exc_info.value.details["error_code"] == "AccessDenied"
