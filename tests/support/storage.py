from typing import Final

import boto3
from botocore.config import Config
from botocore.exceptions import BotoCoreError, ClientError
from mypy_boto3_s3.client import S3Client

DEFAULT_S3_ENDPOINT_URL: Final = "http://localhost:55435"
TEST_S3_REGION: Final = "eu-west-1"
_DELETE_BATCH: Final = 1000


def assertion_client(endpoint_url: str, *, timeout: float = 5, attempts: int = 3) -> S3Client:
    config = Config(
        connect_timeout=timeout,
        read_timeout=timeout,
        retries={"max_attempts": attempts, "mode": "standard"},
        s3={"addressing_style": "path"},
    )
    return boto3.client(  # pyright: ignore[reportUnknownMemberType]
        "s3", endpoint_url=endpoint_url, region_name=TEST_S3_REGION, config=config
    )


def unreachable_reason(endpoint_url: str) -> str | None:
    try:
        assertion_client(endpoint_url, timeout=2, attempts=1).list_buckets()
    except (BotoCoreError, ClientError) as err:
        return str(err)
    return None


def unavailable_message(endpoint_url: str, reason: str) -> str:
    return (
        f"The S3 emulator is not reachable at {endpoint_url}. "
        "Start it with: docker compose up -d --wait s3 "
        "(or set TEST_S3_ENDPOINT_URL)\n"
        f"Reason: {reason}"
    )


def bucket_keys(client: S3Client, bucket: str) -> list[str]:
    paginator = client.get_paginator("list_objects_v2")
    return [
        item["Key"]
        for page in paginator.paginate(Bucket=bucket)
        for item in page.get("Contents", [])
        if "Key" in item
    ]


def empty_bucket(client: S3Client, bucket: str) -> None:
    keys = bucket_keys(client, bucket)
    for start in range(0, len(keys), _DELETE_BATCH):
        chunk = keys[start : start + _DELETE_BATCH]
        client.delete_objects(
            Bucket=bucket, Delete={"Objects": [{"Key": key} for key in chunk], "Quiet": True}
        )
