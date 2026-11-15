import sys
from typing import TYPE_CHECKING, cast

from botocore.exceptions import ClientError
from pydantic import ValidationError

from project_hub.core.config import Settings
from project_hub.storage.s3 import create_s3_client

if TYPE_CHECKING:
    from mypy_boto3_s3.client import S3Client
    from mypy_boto3_s3.literals import BucketLocationConstraintType

_MISSING_BUCKET_CODES = frozenset({"404", "NoSuchBucket", "NotFound"})


def ensure_bucket(client: "S3Client", bucket: str, region: str) -> bool:
    try:
        client.head_bucket(Bucket=bucket)
    except ClientError as err:
        if err.response.get("Error", {}).get("Code") not in _MISSING_BUCKET_CODES:
            raise
    else:
        return False
    if region == "us-east-1":
        client.create_bucket(Bucket=bucket)
    else:
        constraint = cast("BucketLocationConstraintType", region)
        client.create_bucket(
            Bucket=bucket, CreateBucketConfiguration={"LocationConstraint": constraint}
        )
    return True


def main() -> int:
    try:
        settings = Settings()
    except ValidationError as err:
        print(f"Invalid settings: {err}", file=sys.stderr)
        return 1
    if settings.s3_bucket is None:
        print("APP_S3_BUCKET is not set; no bucket to create", file=sys.stderr)
        return 2
    created = ensure_bucket(create_s3_client(settings), settings.s3_bucket, settings.s3_region)
    print(f"Bucket {settings.s3_bucket} {'created' if created else 'already exists'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
