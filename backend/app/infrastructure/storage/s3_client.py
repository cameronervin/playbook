"""S3-compatible storage provider with retry logic and timeouts.

Works with MinIO, AWS S3, and AWS profiles. boto3 calls are synchronous, so each
one is dispatched to a thread executor with an asyncio timeout.
"""

import asyncio
from collections.abc import AsyncGenerator
from functools import partial
from typing import Any, BinaryIO

import boto3
import structlog
from botocore.config import Config as BotoConfig
from botocore.exceptions import BotoCoreError, ClientError

from app.core.config import Settings
from app.core.exceptions import StorageError

from .provider import StorageProvider

logger = structlog.get_logger()


class S3StorageProvider(StorageProvider):
    """S3 storage provider — works with MinIO, AWS S3, and AWS profiles.

    Authentication methods (in order of precedence):
    1. Explicit credentials (S3_ACCESS_KEY_ID + S3_SECRET_ACCESS_KEY) — MinIO.
    2. AWS profile (AWS_PROFILE) — e.g. CLI-issued temporary credentials.
    3. Default AWS credentials chain — default profile or IAM role.

    Environment:
    - MinIO:  S3_ENDPOINT_URL=http://minio:9000 + explicit keys.
    - AWS S3: S3_ENDPOINT_URL=None + profile or explicit keys.
    """

    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        boto_config = BotoConfig(
            signature_version="s3v4",
            region_name=self.settings.S3_REGION,
            s3={"addressing_style": "path"},
            retries={"max_attempts": 3, "mode": "adaptive"},
            connect_timeout=self.settings.S3_TIMEOUT,
            read_timeout=self.settings.S3_TIMEOUT,
        )

        client_kwargs: dict[str, Any] = {
            "service_name": "s3",
            "endpoint_url": self.settings.S3_ENDPOINT_URL or None,
            "config": boto_config,
        }

        if self.settings.S3_ACCESS_KEY_ID and self.settings.S3_SECRET_ACCESS_KEY:
            client_kwargs["aws_access_key_id"] = self.settings.S3_ACCESS_KEY_ID
            client_kwargs["aws_secret_access_key"] = self.settings.S3_SECRET_ACCESS_KEY
            self._client = boto3.client(**client_kwargs)
            logger.info("S3 client initialized with explicit credentials")
        elif self.settings.AWS_PROFILE:
            session = boto3.Session(profile_name=self.settings.AWS_PROFILE)
            self._client = session.client(**client_kwargs)
            logger.info("S3 client initialized with AWS profile", profile=self.settings.AWS_PROFILE)
        else:
            self._client = boto3.client(**client_kwargs)
            logger.info("S3 client initialized with default AWS credentials chain")

        self._bucket = self.settings.S3_BUCKET_NAME
        self._ensure_bucket()

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _ensure_bucket(self) -> None:
        """Create the bucket if it does not exist (useful for local MinIO).

        Connection failures are logged as warnings so the app can still start
        when S3-compatible storage is temporarily unavailable.
        """
        try:
            self._client.head_bucket(Bucket=self._bucket)
        except ClientError:
            logger.info("Creating S3 bucket", bucket=self._bucket)
            try:
                self._client.create_bucket(Bucket=self._bucket)
            except (BotoCoreError, ClientError) as e:
                logger.warning(
                    "Could not create S3 bucket — storage operations will fail until resolved",
                    bucket=self._bucket,
                    error=str(e),
                )
        except BotoCoreError as e:
            logger.warning(
                "S3 endpoint unreachable — storage operations will fail until resolved",
                bucket=self._bucket,
                error=str(e),
            )

    async def _run_sync(self, func: Any, *args: Any, **kwargs: Any) -> Any:
        """Run a synchronous boto3 call in a thread executor with a timeout.

        Raises:
            StorageError: If the operation fails or times out.
        """
        op_name = getattr(func, "__name__", repr(func))
        loop = asyncio.get_running_loop()
        try:
            async with asyncio.timeout(self.settings.S3_TIMEOUT):
                return await loop.run_in_executor(None, partial(func, *args, **kwargs))
        except TimeoutError as te:
            logger.exception("S3 operation timeout", operation=op_name, timeout_seconds=self.settings.S3_TIMEOUT)
            raise StorageError(
                f"S3 operation '{op_name}' timed out after {self.settings.S3_TIMEOUT} seconds",
                retryable=True,
                details={"operation": op_name, "timeout_seconds": self.settings.S3_TIMEOUT},
            ) from te
        except ClientError as e:
            error_code = e.response.get("Error", {}).get("Code", "Unknown")
            retryable = error_code in ("RequestTimeout", "SlowDown", "InternalError", "ServiceUnavailable")
            logger.exception(
                "S3 client error",
                operation=op_name,
                error_code=error_code,
                error=str(e),
                retryable=retryable,
            )
            raise StorageError(
                f"S3 operation '{op_name}' failed: {str(e)}",
                retryable=retryable,
                details={"operation": op_name, "error_code": error_code},
            ) from e
        except Exception as e:
            logger.exception(
                "S3 operation failed",
                operation=op_name,
                error=str(e),
                error_type=type(e).__name__,
            )
            raise StorageError(
                f"S3 operation '{op_name}' failed: {str(e)}",
                retryable=False,
                details={"operation": op_name, "error_type": type(e).__name__},
            ) from e

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def upload_file(self, key: str, file: BinaryIO, content_type: str) -> str:
        await self._run_sync(
            self._client.upload_fileobj,
            file,
            self._bucket,
            key,
            ExtraArgs={"ContentType": content_type},
        )
        logger.info("File uploaded", bucket=self._bucket, key=key)
        return key

    async def download_file(self, key: str) -> bytes:
        response = await self._run_sync(self._client.get_object, Bucket=self._bucket, Key=key)
        body = response["Body"]
        data = await self._run_sync(body.read)
        body.close()
        return data

    async def download_file_stream(
        self, key: str, chunk_size: int = 8 * 1024 * 1024
    ) -> AsyncGenerator[bytes, None]:
        """Stream the S3 object body in chunks, never loading it all into memory."""
        response = await self._run_sync(self._client.get_object, Bucket=self._bucket, Key=key)
        body = response["Body"]
        loop = asyncio.get_running_loop()
        try:
            while True:
                async with asyncio.timeout(self.settings.S3_TIMEOUT):
                    chunk = await loop.run_in_executor(None, body.read, chunk_size)
                if not chunk:
                    break
                yield chunk
        finally:
            body.close()

    async def delete_file(self, key: str) -> None:
        await self._run_sync(self._client.delete_object, Bucket=self._bucket, Key=key)
        logger.info("File deleted", bucket=self._bucket, key=key)

    async def get_presigned_url(
        self, key: str, expires_in: int | None = None, download_filename: str | None = None
    ) -> str:
        expiry = expires_in or self.settings.S3_PRESIGNED_URL_EXPIRY
        params: dict = {"Bucket": self._bucket, "Key": key}
        if download_filename:
            params["ResponseContentDisposition"] = f'attachment; filename="{download_filename}"'

        return await self._run_sync(
            self._client.generate_presigned_url,
            "get_object",
            Params=params,
            ExpiresIn=expiry,
        )

    async def file_exists(self, key: str) -> bool:
        try:
            await self._run_sync(self._client.head_object, Bucket=self._bucket, Key=key)
        except StorageError as e:
            error_code = (e.details or {}).get("error_code", "")
            if error_code in ("404", "NoSuchKey", "NotFound"):
                return False
            raise
        except ClientError:
            return False
        else:
            return True
