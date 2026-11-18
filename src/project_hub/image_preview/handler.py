import json
import logging
import os
import re
import warnings
from collections.abc import Mapping
from io import BytesIO
from typing import Any

import boto3
from botocore.config import Config
from botocore.exceptions import ClientError
from PIL import Image, ImageOps

logger = logging.getLogger("project_hub.image_preview")
# The Lambda Python runtime sets the root logger to WARNING; without this the INFO lines are lost.
logger.setLevel(logging.INFO)

_KEY = re.compile(
    r"projects/([0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12})"
    r"/documents/([0-9A-Za-z_-]+)"
)
_JPEG_SIGNATURE = b"\xff\xd8\xff"
_PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"
# The function has 512 MB and a PNG cannot be reduced while it is decoded.
Image.MAX_IMAGE_PIXELS = 40_000_000
_MAX_SIDE = 512
_QUALITY = 80


class _Skipped(Exception):
    pass


def _s3_client() -> Any:
    endpoint_url = os.environ.get("APP_S3_ENDPOINT_URL") or None
    return boto3.client(  # pyright: ignore[reportUnknownMemberType]
        "s3",
        endpoint_url=endpoint_url,
        region_name=os.environ.get("APP_S3_REGION") or "eu-west-1",
        config=Config(s3={"addressing_style": "path"}) if endpoint_url else None,
    )


def _preview_key(key: str) -> str | None:
    match = _KEY.fullmatch(key)
    return None if match is None else f"projects/{match.group(1)}/previews/{match.group(2)}.jpg"


def _make_preview(data: bytes) -> bytes:
    if not data.startswith((_JPEG_SIGNATURE, _PNG_SIGNATURE)):
        raise _Skipped("not a jpg or png image")
    try:
        # Pillow only warns between one and two times MAX_IMAGE_PIXELS; the warning must refuse too.
        with warnings.catch_warnings():
            warnings.simplefilter("error", Image.DecompressionBombWarning)
            with Image.open(BytesIO(data)) as opened:
                opened.thumbnail((_MAX_SIDE, _MAX_SIDE))
                rgba = ImageOps.exif_transpose(opened).convert("RGBA")
    except Exception as err:
        raise _Skipped(f"image cannot be read: {type(err).__name__}: {err}") from err
    flat = Image.new("RGB", rgba.size, (255, 255, 255))
    flat.paste(rgba, mask=rgba.getchannel("A"))
    out = BytesIO()
    flat.save(out, format="JPEG", quality=_QUALITY)
    return out.getvalue()


def _log(message: str, **fields: str) -> None:
    logger.info(json.dumps({"message": message, **fields}))


def _create_preview(s3: Any, bucket: str, key: str, preview_key: str) -> None:
    try:
        data: bytes = s3.get_object(Bucket=bucket, Key=key)["Body"].read()
    except ClientError as err:
        if err.response.get("Error", {}).get("Code") != "NoSuchKey":
            raise
        _log("image preview skipped", key=key, reason="document no longer exists")
        return
    try:
        preview = _make_preview(data)
    except _Skipped as skipped:
        _log("image preview skipped", key=key, reason=str(skipped))
        return
    s3.put_object(Bucket=bucket, Key=preview_key, Body=preview, ContentType="image/jpeg")
    _log("image preview stored", key=key, preview_key=preview_key)


def handler(event: Mapping[str, Any], context: object) -> None:
    try:
        detail_type = event["detail-type"]
        bucket = event["detail"]["bucket"]["name"]
        key = event["detail"]["object"]["key"]
    except (KeyError, TypeError):
        return
    if not isinstance(bucket, str) or not isinstance(key, str) or not bucket:
        return
    preview_key = _preview_key(key)
    if preview_key is None:
        return
    if detail_type == "Object Created":
        _create_preview(_s3_client(), bucket, key, preview_key)
    elif detail_type == "Object Deleted":
        _s3_client().delete_object(Bucket=bucket, Key=preview_key)
        _log("image preview deleted", key=key, preview_key=preview_key)
