import json
import logging
from collections.abc import Iterator
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime, timedelta
from typing import Any, cast
from uuid import UUID, uuid4

import boto3
import psycopg
import pytest
from mypy_boto3_s3.client import S3Client

from project_hub.storage_usage.handler import handler, project_id_from_key
from tests.support.storage import TEST_S3_REGION
from tests.support.storage_usage import (
    created_event,
    eventbridge_event,
    sqs_event,
    sqs_record,
)


@pytest.fixture(autouse=True)
def lambda_env(
    monkeypatch: pytest.MonkeyPatch, migrated_database_url: str, s3_endpoint_url: str
) -> None:
    monkeypatch.setenv("APP_DATABASE_URL", migrated_database_url)
    monkeypatch.setenv("APP_S3_ENDPOINT_URL", s3_endpoint_url)
    monkeypatch.setenv("APP_S3_REGION", TEST_S3_REGION)


@pytest.fixture
def project_id(migrated_database_url: str) -> Iterator[UUID]:
    user_id = uuid4()
    pid = uuid4()
    with psycopg.connect(migrated_database_url, autocommit=True) as conn:
        conn.execute(
            "INSERT INTO users (id, login, password_hash) VALUES (%s, %s, 'x')",
            (user_id, f"u-{user_id.hex}"),
        )
        conn.execute(
            "INSERT INTO projects (id, owner_id, name) VALUES (%s, %s, 'P')", (pid, user_id)
        )
    yield pid
    with psycopg.connect(migrated_database_url, autocommit=True) as conn:
        conn.execute("DELETE FROM projects WHERE id = %s", (pid,))
        conn.execute("DELETE FROM users WHERE id = %s", (user_id,))


def doc_key(pid: UUID) -> str:
    return f"projects/{pid}/documents/{uuid4().hex}"


def put(s3: S3Client, bucket: str, key: str, size: int) -> None:
    s3.put_object(Bucket=bucket, Key=key, Body=b"x" * size)


def stored(url: str, pid: UUID) -> tuple[int, datetime | None]:
    with psycopg.connect(url) as conn:
        row = conn.execute(
            "SELECT storage_used_bytes, storage_counted_at FROM projects WHERE id = %s", (pid,)
        ).fetchone()
    assert row is not None
    return row[0], row[1]


def test_created_event_stores_sum_of_objects(
    migrated_database_url: str, s3_client: S3Client, storage_bucket: str, project_id: UUID
) -> None:
    first, second = doc_key(project_id), doc_key(project_id)
    put(s3_client, storage_bucket, first, 100)
    put(s3_client, storage_bucket, second, 23)
    before = datetime.now(UTC)

    result = handler(created_event(storage_bucket, first), None)

    assert result == {"batchItemFailures": []}
    used, counted_at = stored(migrated_database_url, project_id)
    assert used == 123
    assert counted_at is not None
    assert counted_at >= before


def test_other_projects_objects_are_not_counted(
    migrated_database_url: str, s3_client: S3Client, storage_bucket: str, project_id: UUID
) -> None:
    mine = doc_key(project_id)
    put(s3_client, storage_bucket, mine, 10)
    put(s3_client, storage_bucket, doc_key(uuid4()), 500)

    handler(created_event(storage_bucket, mine), None)

    assert stored(migrated_database_url, project_id)[0] == 10


def test_deleted_event_counts_what_is_left(
    migrated_database_url: str, s3_client: S3Client, storage_bucket: str, project_id: UUID
) -> None:
    kept, removed = doc_key(project_id), doc_key(project_id)
    put(s3_client, storage_bucket, kept, 40)
    put(s3_client, storage_bucket, removed, 60)
    s3_client.delete_object(Bucket=storage_bucket, Key=removed)
    body = json.dumps(eventbridge_event(storage_bucket, removed, "Object Deleted"))

    result = handler(sqs_event(sqs_record("m1", body)), None)

    assert result == {"batchItemFailures": []}
    assert stored(migrated_database_url, project_id)[0] == 40


def test_deleted_event_stores_zero_when_nothing_is_left(
    migrated_database_url: str, storage_bucket: str, project_id: UUID
) -> None:
    with psycopg.connect(migrated_database_url, autocommit=True) as conn:
        conn.execute("UPDATE projects SET storage_used_bytes = 99 WHERE id = %s", (project_id,))
    body = json.dumps(eventbridge_event(storage_bucket, doc_key(project_id), "Object Deleted"))

    handler(sqs_event(sqs_record("m1", body)), None)

    used, counted_at = stored(migrated_database_url, project_id)
    assert used == 0
    assert counted_at is not None


def test_one_count_per_project_per_batch(
    migrated_database_url: str, s3_client: S3Client, storage_bucket: str, project_id: UUID
) -> None:
    keys = [doc_key(project_id) for _ in range(3)]
    for key in keys:
        put(s3_client, storage_bucket, key, 7)
    event = sqs_event(
        *(
            sqs_record(f"m{i}", json.dumps(eventbridge_event(storage_bucket, key)))
            for i, key in enumerate(keys)
        )
    )

    result = handler(event, None)

    assert result == {"batchItemFailures": []}
    assert stored(migrated_database_url, project_id)[0] == 21


def test_counted_project_is_logged(
    caplog: pytest.LogCaptureFixture,
    s3_client: S3Client,
    storage_bucket: str,
    project_id: UUID,
) -> None:
    key = doc_key(project_id)
    put(s3_client, storage_bucket, key, 5)

    with caplog.at_level(logging.INFO):
        handler(created_event(storage_bucket, key), None)

    lines = [
        json.loads(r.getMessage()) for r in caplog.records if "storage usage" in r.getMessage()
    ]
    assert lines == [
        {"message": "storage usage counted", "project_id": str(project_id), "bytes": 5}
    ]


def _usage_lines(caplog: pytest.LogCaptureFixture) -> list[dict[str, Any]]:
    return [json.loads(r.getMessage()) for r in caplog.records if "storage usage" in r.getMessage()]


def test_count_for_unknown_project_is_logged_as_not_stored(
    caplog: pytest.LogCaptureFixture, s3_client: S3Client, storage_bucket: str
) -> None:
    ghost = uuid4()
    key = doc_key(ghost)
    put(s3_client, storage_bucket, key, 9)

    with caplog.at_level(logging.INFO):
        handler(created_event(storage_bucket, key), None)

    assert _usage_lines(caplog) == [
        {
            "message": "storage usage not stored",
            "project_id": str(ghost),
            "bytes": 9,
            "reason": "project deleted or counted later",
        }
    ]


def test_older_count_is_logged_as_not_stored(
    caplog: pytest.LogCaptureFixture,
    migrated_database_url: str,
    s3_client: S3Client,
    storage_bucket: str,
    project_id: UUID,
) -> None:
    with psycopg.connect(migrated_database_url, autocommit=True) as conn:
        conn.execute(
            "UPDATE projects SET storage_counted_at = %s WHERE id = %s",
            (datetime.now(UTC) + timedelta(hours=1), project_id),
        )
    key = doc_key(project_id)
    put(s3_client, storage_bucket, key, 4)

    with caplog.at_level(logging.INFO):
        handler(created_event(storage_bucket, key), None)

    assert [line["message"] for line in _usage_lines(caplog)] == ["storage usage not stored"]


def test_unknown_project_is_not_a_failure(
    migrated_database_url: str, s3_client: S3Client, storage_bucket: str, project_id: UUID
) -> None:
    ghost = uuid4()
    key = doc_key(ghost)
    put(s3_client, storage_bucket, key, 9)

    result = handler(created_event(storage_bucket, key), None)

    assert result == {"batchItemFailures": []}
    assert stored(migrated_database_url, project_id) == (0, None)


@pytest.mark.parametrize(
    "key",
    [
        "other/file",
        "projects/not-a-uuid/documents/abc",
        f"projects/{uuid4()}/documents/",
        f"projects/{uuid4()}/avatars/abc",
        f"projects/{uuid4()}",
    ],
)
def test_key_outside_projects_is_ignored(
    migrated_database_url: str, storage_bucket: str, project_id: UUID, key: str
) -> None:
    result = handler(created_event(storage_bucket, key), None)

    assert result == {"batchItemFailures": []}
    assert stored(migrated_database_url, project_id) == (0, None)


@pytest.mark.parametrize(
    "body",
    ["not json", "[]", "null", "{}", '{"detail": 1}', '{"detail": {"bucket": {}, "object": {}}}'],
)
def test_malformed_body_is_ignored(migrated_database_url: str, project_id: UUID, body: str) -> None:
    result = handler(sqs_event(sqs_record("m1", body)), None)

    assert result == {"batchItemFailures": []}
    assert stored(migrated_database_url, project_id) == (0, None)


def test_older_count_does_not_overwrite_newer(
    migrated_database_url: str, s3_client: S3Client, storage_bucket: str, project_id: UUID
) -> None:
    future = datetime.now(UTC) + timedelta(hours=1)
    with psycopg.connect(migrated_database_url, autocommit=True) as conn:
        conn.execute(
            "UPDATE projects SET storage_used_bytes = 5, storage_counted_at = %s WHERE id = %s",
            (future, project_id),
        )
    key = doc_key(project_id)
    put(s3_client, storage_bucket, key, 300)

    result = handler(created_event(storage_bucket, key), None)

    assert result == {"batchItemFailures": []}
    assert stored(migrated_database_url, project_id) == (5, future)


def test_more_than_1000_objects_are_counted(
    migrated_database_url: str, s3_client: S3Client, storage_bucket: str, project_id: UUID
) -> None:
    keys = [doc_key(project_id) for _ in range(1001)]
    with ThreadPoolExecutor(max_workers=16) as pool:
        for future in [pool.submit(put, s3_client, storage_bucket, k, 2) for k in keys]:
            future.result()

    handler(created_event(storage_bucket, keys[0]), None)

    assert stored(migrated_database_url, project_id)[0] == 2002


def test_database_error_reports_the_messages_of_that_project(
    monkeypatch: pytest.MonkeyPatch, s3_client: S3Client, storage_bucket: str, project_id: UUID
) -> None:
    monkeypatch.setenv("APP_DATABASE_URL", "postgresql://u:p@127.0.0.1:1/x?connect_timeout=1")
    key = doc_key(project_id)
    put(s3_client, storage_bucket, key, 1)
    event = sqs_event(
        sqs_record("a", json.dumps(eventbridge_event(storage_bucket, key))),
        sqs_record("b", json.dumps(eventbridge_event(storage_bucket, key))),
        sqs_record("c", "garbage"),
    )

    result = handler(event, None)

    assert result == {"batchItemFailures": [{"itemIdentifier": "a"}, {"itemIdentifier": "b"}]}


def test_one_project_failing_does_not_stop_the_others(
    migrated_database_url: str, s3_client: S3Client, storage_bucket: str, project_id: UUID
) -> None:
    key = doc_key(project_id)
    put(s3_client, storage_bucket, key, 11)
    event = sqs_event(
        sqs_record("bad", json.dumps(eventbridge_event("no-such-bucket-xyz", doc_key(uuid4())))),
        sqs_record("good", json.dumps(eventbridge_event(storage_bucket, key))),
    )

    result = handler(event, None)

    assert result == {"batchItemFailures": [{"itemIdentifier": "bad"}]}
    assert stored(migrated_database_url, project_id)[0] == 11


def test_sqlalchemy_driver_prefix_in_the_url_is_accepted(
    monkeypatch: pytest.MonkeyPatch,
    migrated_database_url: str,
    s3_client: S3Client,
    storage_bucket: str,
    project_id: UUID,
) -> None:
    monkeypatch.setenv(
        "APP_DATABASE_URL", "postgresql+psycopg://" + migrated_database_url.partition("://")[2]
    )
    key = doc_key(project_id)
    put(s3_client, storage_bucket, key, 8)

    result = handler(created_event(storage_bucket, key), None)

    assert result == {"batchItemFailures": []}
    assert stored(migrated_database_url, project_id)[0] == 8


def test_database_url_is_read_from_ssm_parameter(
    monkeypatch: pytest.MonkeyPatch,
    migrated_database_url: str,
    s3_endpoint_url: str,
    s3_client: S3Client,
    storage_bucket: str,
    project_id: UUID,
) -> None:
    name = f"/project-hub/test-{uuid4().hex}"
    monkeypatch.setenv("AWS_ENDPOINT_URL_SSM", s3_endpoint_url)
    monkeypatch.setenv("AWS_DEFAULT_REGION", TEST_S3_REGION)
    ssm = cast("Any", boto3.client("ssm", endpoint_url=s3_endpoint_url, region_name=TEST_S3_REGION))  # pyright: ignore[reportUnknownMemberType]
    ssm.put_parameter(Name=name, Value=migrated_database_url, Type="SecureString")
    monkeypatch.delenv("APP_DATABASE_URL")
    monkeypatch.setenv("APP_DATABASE_URL_PARAMETER", name)
    key = doc_key(project_id)
    put(s3_client, storage_bucket, key, 12)

    first = handler(created_event(storage_bucket, key), None)
    ssm.delete_parameter(Name=name)
    second = handler(created_event(storage_bucket, key), None)

    assert first == second == {"batchItemFailures": []}
    assert stored(migrated_database_url, project_id)[0] == 12


def test_project_id_from_key() -> None:
    pid = uuid4()
    assert project_id_from_key(f"projects/{pid}/documents/abc") == pid
    assert project_id_from_key(f"projects/{pid}/documents/a/b") == pid
    assert project_id_from_key(f"projects/{pid}/documents/") is None
    assert project_id_from_key("projects/x/documents/abc") is None
