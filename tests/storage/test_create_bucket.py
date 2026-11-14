import os
import subprocess
import sys
from collections.abc import Iterator
from pathlib import Path
from uuid import uuid4

import pytest
from botocore.exceptions import ClientError
from mypy_boto3_s3.client import S3Client

from project_hub.storage.create_bucket import ensure_bucket
from project_hub.storage.s3 import create_s3_client
from tests.isolated_settings import IsolatedSettings
from tests.support.storage import TEST_S3_REGION


def _bucket_exists(client: S3Client, bucket: str) -> bool:
    try:
        client.head_bucket(Bucket=bucket)
    except ClientError:
        return False
    return True


@pytest.fixture
def new_bucket(s3_client: S3Client) -> Iterator[str]:
    bucket = f"project-hub-test-{uuid4().hex}"
    try:
        yield bucket
    finally:
        if _bucket_exists(s3_client, bucket):
            s3_client.delete_bucket(Bucket=bucket)


def _run_create_bucket(tmp_path: Path, **app_env: str) -> subprocess.CompletedProcess[str]:
    empty_file = tmp_path / "empty"
    empty_file.write_text("", encoding="utf-8")
    env = {key: value for key, value in os.environ.items() if not key.startswith(("APP_", "AWS_"))}
    env |= {
        "AWS_ACCESS_KEY_ID": "test",
        "AWS_SECRET_ACCESS_KEY": "test",
        "AWS_SHARED_CREDENTIALS_FILE": str(empty_file),
        "AWS_CONFIG_FILE": str(empty_file),
        **app_env,
    }
    return subprocess.run(
        [sys.executable, "-m", "project_hub.storage.create_bucket"],
        capture_output=True,
        text=True,
        cwd=tmp_path,
        env=env,
        timeout=60,
        check=False,
    )


def test_creates_missing_bucket_then_noop(
    s3_endpoint_url: str, s3_client: S3Client, new_bucket: str
) -> None:
    settings = IsolatedSettings(s3_endpoint_url=s3_endpoint_url, s3_region=TEST_S3_REGION)
    client = create_s3_client(settings)

    assert ensure_bucket(client, new_bucket, TEST_S3_REGION) is True
    assert _bucket_exists(s3_client, new_bucket)
    assert ensure_bucket(client, new_bucket, TEST_S3_REGION) is False


def test_creates_bucket_in_us_east_1(
    s3_endpoint_url: str, s3_client: S3Client, new_bucket: str
) -> None:
    settings = IsolatedSettings(s3_endpoint_url=s3_endpoint_url, s3_region="us-east-1")

    assert ensure_bucket(create_s3_client(settings), new_bucket, "us-east-1") is True
    assert _bucket_exists(s3_client, new_bucket)


def test_main_without_bucket_setting_exits_2(tmp_path: Path, s3_endpoint_url: str) -> None:
    result = _run_create_bucket(tmp_path, APP_S3_ENDPOINT_URL=s3_endpoint_url)

    assert result.returncode == 2, result.stderr
    assert "APP_S3_BUCKET" in result.stderr


def test_main_creates_configured_bucket(
    tmp_path: Path, s3_endpoint_url: str, s3_client: S3Client, new_bucket: str
) -> None:
    result = _run_create_bucket(
        tmp_path,
        APP_S3_BUCKET=new_bucket,
        APP_S3_ENDPOINT_URL=s3_endpoint_url,
        APP_S3_REGION=TEST_S3_REGION,
    )

    assert result.returncode == 0, result.stderr
    assert _bucket_exists(s3_client, new_bucket)
