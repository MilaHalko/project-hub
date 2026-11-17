import json
import logging
import os
import re
from collections import defaultdict
from collections.abc import Mapping
from datetime import UTC, datetime
from functools import cache
from typing import Any, cast
from uuid import UUID

import boto3
import psycopg
from botocore.config import Config
from botocore.exceptions import BotoCoreError, ClientError

logger = logging.getLogger("project_hub.storage_usage")
# The Lambda Python runtime sets the root logger to WARNING; without this the INFO lines are lost.
logger.setLevel(logging.INFO)

_KEY = re.compile(
    r"projects/([0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12})/documents/.+",
    re.DOTALL,
)
_DRIVER_SUFFIX = re.compile(r"^(postgres(?:ql)?)\+\w+://")
_UPDATE = (
    "UPDATE projects SET storage_used_bytes = %s, storage_counted_at = %s "
    "WHERE id = %s AND (storage_counted_at IS NULL OR storage_counted_at < %s)"
)


def project_id_from_key(key: str) -> UUID | None:
    match = _KEY.fullmatch(key)
    return UUID(match.group(1)) if match else None


def _record_target(record: Mapping[str, Any]) -> tuple[str, UUID] | None:
    try:
        detail = json.loads(record["body"])["detail"]
        bucket = detail["bucket"]["name"]
        key = detail["object"]["key"]
    except (KeyError, TypeError, ValueError):
        return None
    if not isinstance(bucket, str) or not isinstance(key, str) or not bucket:
        return None
    project_id = project_id_from_key(key)
    return None if project_id is None else (bucket, project_id)


@cache
def _database_url_from_parameter(name: str) -> str:
    ssm = cast("Any", boto3.client("ssm"))  # pyright: ignore[reportUnknownMemberType]
    value: str = ssm.get_parameter(Name=name, WithDecryption=True)["Parameter"]["Value"]
    return value


def _database_url() -> str:
    url = os.environ.get("APP_DATABASE_URL")
    if not url:
        url = _database_url_from_parameter(os.environ["APP_DATABASE_URL_PARAMETER"])
    return _DRIVER_SUFFIX.sub(r"\1://", url)


def _s3_client() -> Any:
    endpoint_url = os.environ.get("APP_S3_ENDPOINT_URL") or None
    return boto3.client(  # pyright: ignore[reportUnknownMemberType]
        "s3",
        endpoint_url=endpoint_url,
        region_name=os.environ.get("APP_S3_REGION") or "eu-west-1",
        config=Config(s3={"addressing_style": "path"}) if endpoint_url else None,
    )


def _total_bytes(s3: Any, bucket: str, project_id: UUID) -> int:
    total = 0
    pages = s3.get_paginator("list_objects_v2").paginate(
        Bucket=bucket, Prefix=f"projects/{project_id}/documents/"
    )
    for page in pages:
        total += sum(item["Size"] for item in page.get("Contents", ()))
    return total


def handler(event: Mapping[str, Any], context: object) -> dict[str, list[dict[str, str]]]:
    targets: dict[tuple[str, UUID], list[str]] = defaultdict(list)
    for record in event.get("Records", ()):
        target = _record_target(record)
        if target is not None:
            targets[target].append(record["messageId"])
    failed: list[str] = []
    if targets:
        try:
            with psycopg.connect(_database_url(), autocommit=True, connect_timeout=5) as conn:
                s3 = _s3_client()
                for (bucket, project_id), message_ids in targets.items():
                    try:
                        counted_at = datetime.now(UTC)
                        used = _total_bytes(s3, bucket, project_id)
                        stored = conn.execute(
                            _UPDATE, (used, counted_at, project_id, counted_at)
                        ).rowcount
                    except (psycopg.Error, BotoCoreError, ClientError):
                        logger.exception("storage usage failed for project %s", project_id)
                        failed.extend(message_ids)
                    else:
                        line: dict[str, object] = {
                            "message": "storage usage counted",
                            "project_id": str(project_id),
                            "bytes": used,
                        }
                        if stored != 1:
                            line["message"] = "storage usage not stored"
                            line["reason"] = "project deleted or counted later"
                        logger.info(json.dumps(line))
        except (psycopg.Error, BotoCoreError, ClientError, KeyError):
            logger.exception("storage usage failed to start")
            failed = [mid for ids in targets.values() for mid in ids]
    return {"batchItemFailures": [{"itemIdentifier": mid} for mid in failed]}
