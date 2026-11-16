import asyncio
import logging
from collections.abc import Sequence
from typing import TYPE_CHECKING, Final

import boto3
from botocore.config import Config
from botocore.exceptions import BotoCoreError, ClientError

from project_hub.core.config import Settings
from project_hub.storage.files import StorageUnavailableError

if TYPE_CHECKING:
    from mypy_boto3_s3.client import S3Client

logger = logging.getLogger(__name__)

_DELETE_BATCH: Final = 1000
_ERRORS = (BotoCoreError, ClientError)


def create_s3_client(settings: Settings) -> "S3Client":
    config = Config(
        connect_timeout=5,
        read_timeout=30,
        retries={"max_attempts": 3, "mode": "standard"},
        max_pool_connections=20,
    )
    if settings.s3_endpoint_url is not None:
        config = config.merge(Config(s3={"addressing_style": "path"}))
    return boto3.client(  # pyright: ignore[reportUnknownMemberType]
        "s3",
        endpoint_url=settings.s3_endpoint_url,
        region_name=settings.s3_region,
        config=config,
    )


class S3FileStorage:
    def __init__(self, client: "S3Client", bucket: str) -> None:
        self._client = client
        self._bucket = bucket

    async def put(self, key: str, data: bytes, content_type: str) -> None:
        try:
            await asyncio.to_thread(
                self._client.put_object,
                Bucket=self._bucket,
                Key=key,
                Body=data,
                ContentType=content_type,
            )
        except _ERRORS as err:
            raise self._unavailable("put") from err

    async def get(self, key: str) -> bytes:
        try:
            return await asyncio.to_thread(self._read, key)
        except _ERRORS as err:
            raise self._unavailable("get") from err

    async def get_if_exists(self, key: str) -> bytes | None:
        try:
            return await asyncio.to_thread(self._read, key)
        except self._client.exceptions.NoSuchKey:
            return None
        except _ERRORS as err:
            raise self._unavailable("get") from err

    async def delete(self, keys: Sequence[str]) -> None:
        for start in range(0, len(keys), _DELETE_BATCH):
            chunk = keys[start : start + _DELETE_BATCH]
            try:
                response = await asyncio.to_thread(
                    self._client.delete_objects,
                    Bucket=self._bucket,
                    Delete={"Objects": [{"Key": key} for key in chunk], "Quiet": True},
                )
            except _ERRORS as err:
                raise self._unavailable("delete") from err
            errors = response.get("Errors", [])
            if errors:
                logger.error(
                    "file storage delete failed for %d keys",
                    len(errors),
                    extra={
                        "event": "file storage failed",
                        "operation": "delete",
                        "bucket": self._bucket,
                        "errors": errors,
                    },
                )
                raise StorageUnavailableError()

    def _read(self, key: str) -> bytes:
        response = self._client.get_object(Bucket=self._bucket, Key=key)
        return response["Body"].read()

    def _unavailable(self, operation: str) -> StorageUnavailableError:
        logger.exception(
            "file storage %s failed",
            operation,
            extra={"event": "file storage failed", "operation": operation, "bucket": self._bucket},
        )
        return StorageUnavailableError()


def create_s3_storage(settings: Settings) -> S3FileStorage | None:
    if settings.s3_bucket is None:
        logger.warning("APP_S3_BUCKET is not set; documents are disabled")
        return None
    return S3FileStorage(create_s3_client(settings), settings.s3_bucket)
