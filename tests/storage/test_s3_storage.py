import asyncio
import logging
import time
from collections.abc import Iterator
from typing import Any
from uuid import uuid4

import pytest
from mypy_boto3_s3.client import S3Client

from project_hub.storage.files import StorageUnavailableError, discard_quietly
from project_hub.storage.s3 import S3FileStorage, create_s3_client, create_s3_storage
from tests.isolated_settings import IsolatedSettings
from tests.support.storage import TEST_S3_REGION, bucket_keys, empty_bucket

pytestmark = pytest.mark.anyio

PDF = b"%PDF-1.4 x"


def _field(record: logging.LogRecord, name: str) -> object:
    return getattr(record, name)


def _storage(bucket: str, endpoint_url: str) -> S3FileStorage:
    storage = create_s3_storage(
        IsolatedSettings(s3_bucket=bucket, s3_endpoint_url=endpoint_url, s3_region=TEST_S3_REGION)
    )
    assert storage is not None
    return storage


@pytest.fixture
def storage(
    storage_bucket: str, s3_endpoint_url: str, s3_client: S3Client
) -> Iterator[S3FileStorage]:
    try:
        yield _storage(storage_bucket, s3_endpoint_url)
    finally:
        empty_bucket(s3_client, storage_bucket)


@pytest.fixture
def missing_bucket_storage(s3_endpoint_url: str) -> S3FileStorage:
    return _storage(f"project-hub-missing-{uuid4().hex}", s3_endpoint_url)


async def test_put_then_get_returns_same_bytes(
    storage: S3FileStorage, s3_client: S3Client, storage_bucket: str
) -> None:
    key = "projects/p/documents/k"

    await storage.put(key, PDF, "application/pdf")

    assert await storage.get(key) == PDF
    head = s3_client.head_object(Bucket=storage_bucket, Key=key)
    assert head["ContentType"] == "application/pdf"


async def test_delete_removes_several_keys(
    storage: S3FileStorage, s3_client: S3Client, storage_bucket: str
) -> None:
    for key in ("a", "b", "c"):
        await storage.put(key, PDF, "application/pdf")

    await storage.delete(["a", "b"])

    assert bucket_keys(s3_client, storage_bucket) == ["c"]


async def test_delete_accepts_empty_list_and_missing_keys(storage: S3FileStorage) -> None:
    await storage.delete([])
    await storage.delete(["nope"])


async def test_delete_more_than_1000_keys(
    storage: S3FileStorage, s3_endpoint_url: str, s3_client: S3Client, storage_bucket: str
) -> None:
    keys = [f"many/{n:04d}" for n in range(1001)]
    await asyncio.gather(*(storage.put(key, b"x", "application/pdf") for key in keys))
    assert len(bucket_keys(s3_client, storage_bucket)) == 1001
    client = create_s3_client(
        IsolatedSettings(s3_endpoint_url=s3_endpoint_url, s3_region=TEST_S3_REGION)
    )
    batch_sizes: list[int] = []

    def record_batch(params: dict[str, Any], **_: Any) -> None:
        batch_sizes.append(len(params["Delete"]["Objects"]))

    client.meta.events.register("before-parameter-build.s3.DeleteObjects", record_batch)

    await S3FileStorage(client, storage_bucket).delete(keys)

    assert bucket_keys(s3_client, storage_bucket) == []
    assert batch_sizes == [1000, 1]


async def test_missing_bucket_raises_storage_unavailable(
    missing_bucket_storage: S3FileStorage,
) -> None:
    with pytest.raises(StorageUnavailableError):
        await missing_bucket_storage.put("k", PDF, "application/pdf")
    with pytest.raises(StorageUnavailableError):
        await missing_bucket_storage.get("k")
    with pytest.raises(StorageUnavailableError):
        await missing_bucket_storage.delete(["k"])


async def test_unreachable_endpoint_raises_storage_unavailable() -> None:
    storage = _storage("project-hub-documents", "http://127.0.0.1:9")
    started = time.monotonic()

    with pytest.raises(StorageUnavailableError):
        await storage.put("k", PDF, "application/pdf")

    assert time.monotonic() - started < 15


async def test_get_missing_key_raises_storage_unavailable(storage: S3FileStorage) -> None:
    with pytest.raises(StorageUnavailableError):
        await storage.get("projects/p/documents/missing")


async def test_storage_unavailable_has_fixed_message(
    missing_bucket_storage: S3FileStorage,
) -> None:
    with pytest.raises(StorageUnavailableError) as exc_info:
        await missing_bucket_storage.get("k")

    assert exc_info.value.message == "File storage is unavailable"


async def test_failure_is_logged_with_its_cause(
    missing_bucket_storage: S3FileStorage, caplog: pytest.LogCaptureFixture
) -> None:
    with (
        caplog.at_level(logging.ERROR, logger="project_hub.storage.s3"),
        pytest.raises(StorageUnavailableError) as exc_info,
    ):
        await missing_bucket_storage.put("k", PDF, "application/pdf")

    records = [r for r in caplog.records if r.name == "project_hub.storage.s3"]
    assert len(records) == 1
    assert records[0].levelno == logging.ERROR
    assert records[0].exc_info is not None
    assert exc_info.value.__cause__ is records[0].exc_info[1]


async def test_discard_quietly_logs_warning_on_failure(
    missing_bucket_storage: S3FileStorage, caplog: pytest.LogCaptureFixture
) -> None:
    project_id = uuid4()

    with caplog.at_level(logging.WARNING, logger="project_hub.storage.files"):
        await discard_quietly(missing_bucket_storage, ["k"], project_id=project_id)

    records = [r for r in caplog.records if r.name == "project_hub.storage.files"]
    assert len(records) == 1
    record = records[0]
    assert record.levelno == logging.WARNING
    assert record.getMessage().startswith("document files left in storage")
    assert _field(record, "event") == "document files left in storage"
    assert _field(record, "keys") == ["k"]
    assert _field(record, "project_id") == project_id


async def test_discard_quietly_deletes_the_files(
    storage: S3FileStorage, s3_client: S3Client, storage_bucket: str
) -> None:
    await storage.put("a", PDF, "application/pdf")

    await discard_quietly(storage, ["a"], project_id=uuid4())

    assert bucket_keys(s3_client, storage_bucket) == []
