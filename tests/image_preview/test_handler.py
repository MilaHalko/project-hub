import json
import logging
import struct
import zlib
from io import BytesIO
from typing import Any
from uuid import uuid4

import pytest
from botocore.exceptions import ClientError
from mypy_boto3_s3.client import S3Client
from PIL import Image, ImageOps

from project_hub.image_preview import handler as handler_module
from project_hub.image_preview.handler import handler
from tests.support.image_preview import image_bytes, object_event
from tests.support.storage import TEST_S3_REGION


@pytest.fixture(autouse=True)
def lambda_env(monkeypatch: pytest.MonkeyPatch, s3_endpoint_url: str) -> None:
    monkeypatch.setenv("APP_S3_ENDPOINT_URL", s3_endpoint_url)
    monkeypatch.setenv("APP_S3_REGION", TEST_S3_REGION)


def keys(project_id: str | None = None, name: str | None = None) -> tuple[str, str]:
    pid = project_id or str(uuid4())
    name = name or uuid4().hex
    return f"projects/{pid}/documents/{name}", f"projects/{pid}/previews/{name}.jpg"


def put(s3: S3Client, bucket: str, key: str, body: bytes) -> None:
    s3.put_object(Bucket=bucket, Key=key, Body=body)


def preview_of(s3: S3Client, bucket: str, key: str) -> Image.Image:
    response = s3.get_object(Bucket=bucket, Key=key)
    assert response["ContentType"] == "image/jpeg"
    image = Image.open(BytesIO(response["Body"].read()))
    image.load()
    return image


def corner_pixel(image: Image.Image) -> tuple[int, ...]:
    pixel = image.convert("RGB").getpixel((10, 10))
    assert isinstance(pixel, tuple)
    return pixel


def has_object(s3: S3Client, bucket: str, key: str) -> bool:
    return s3.list_objects_v2(Bucket=bucket, Prefix=key).get("KeyCount", 0) == 1


def run(bucket: str, key: str, detail_type: str = "Object Created") -> None:
    assert handler(object_event(bucket, key, detail_type), None) is None


def test_png_with_alpha_becomes_a_jpeg_that_fits_and_keeps_the_ratio(
    s3_client: S3Client, storage_bucket: str
) -> None:
    doc, preview = keys()
    put(s3_client, storage_bucket, doc, image_bytes((2000, 1000), "PNG", "RGBA", (0, 0, 0, 0)))
    run(storage_bucket, doc)
    image = preview_of(s3_client, storage_bucket, preview)
    assert image.format == "JPEG"
    assert image.size == (512, 256)


def test_transparent_pixels_are_flattened_onto_white(
    s3_client: S3Client, storage_bucket: str
) -> None:
    doc, preview = keys()
    put(s3_client, storage_bucket, doc, image_bytes((600, 600), "PNG", "RGBA", (255, 0, 0, 0)))
    run(storage_bucket, doc)
    assert min(corner_pixel(preview_of(s3_client, storage_bucket, preview))) >= 250


def test_palette_png_with_transparency_is_flattened_onto_white(
    s3_client: S3Client, storage_bucket: str
) -> None:
    doc, preview = keys()
    source = Image.new("RGBA", (600, 600), (255, 0, 0, 0)).convert("P")
    source.info["transparency"] = 0
    out = BytesIO()
    source.save(out, format="PNG", transparency=0)
    put(s3_client, storage_bucket, doc, out.getvalue())
    run(storage_bucket, doc)
    assert min(corner_pixel(preview_of(s3_client, storage_bucket, preview))) >= 250


def test_small_jpeg_is_not_enlarged(s3_client: S3Client, storage_bucket: str) -> None:
    doc, preview = keys()
    put(s3_client, storage_bucket, doc, image_bytes((100, 50), "JPEG"))
    run(storage_bucket, doc)
    assert preview_of(s3_client, storage_bucket, preview).size == (100, 50)


def test_tall_image_fits_the_height(s3_client: S3Client, storage_bucket: str) -> None:
    doc, preview = keys()
    put(s3_client, storage_bucket, doc, image_bytes((1000, 3000), "JPEG"))
    run(storage_bucket, doc)
    size = preview_of(s3_client, storage_bucket, preview).size
    assert size[1] == 512
    assert abs(size[0] - 171) <= 1


def test_exif_orientation_is_applied(s3_client: S3Client, storage_bucket: str) -> None:
    doc, preview = keys()
    put(s3_client, storage_bucket, doc, image_bytes((400, 200), "JPEG", orientation=6))
    run(storage_bucket, doc)
    assert preview_of(s3_client, storage_bucket, preview).size == (200, 400)


def test_creating_the_document_again_overwrites_the_preview(
    s3_client: S3Client, storage_bucket: str
) -> None:
    doc, preview = keys()
    put(s3_client, storage_bucket, doc, image_bytes((100, 50), "PNG"))
    run(storage_bucket, doc)
    put(s3_client, storage_bucket, doc, image_bytes((50, 100), "PNG"))
    run(storage_bucket, doc)
    assert preview_of(s3_client, storage_bucket, preview).size == (50, 100)


def test_logs_stored_with_the_preview_key(
    s3_client: S3Client, storage_bucket: str, caplog: pytest.LogCaptureFixture
) -> None:
    doc, preview = keys()
    put(s3_client, storage_bucket, doc, image_bytes((10, 10), "PNG"))
    with caplog.at_level(logging.INFO, logger="project_hub.image_preview"):
        run(storage_bucket, doc)
    lines = [json.loads(r.getMessage()) for r in caplog.records]
    assert lines == [{"message": "image preview stored", "key": doc, "preview_key": preview}]


def log_lines(caplog: pytest.LogCaptureFixture) -> list[dict[str, Any]]:
    return [json.loads(r.getMessage()) for r in caplog.records]


def test_pdf_object_gets_no_preview(
    s3_client: S3Client, storage_bucket: str, caplog: pytest.LogCaptureFixture
) -> None:
    doc, preview = keys()
    put(s3_client, storage_bucket, doc, b"%PDF-1.7\n" + b"x" * 100)
    with caplog.at_level(logging.INFO, logger="project_hub.image_preview"):
        run(storage_bucket, doc)
    assert not has_object(s3_client, storage_bucket, preview)
    (line,) = log_lines(caplog)
    assert line["message"] == "image preview skipped"
    assert line["key"] == doc
    assert line["reason"]


def test_image_signature_with_garbage_content_gets_no_preview(
    s3_client: S3Client, storage_bucket: str, caplog: pytest.LogCaptureFixture
) -> None:
    doc, preview = keys()
    put(s3_client, storage_bucket, doc, b"\xff\xd8\xff" + b"garbage" * 20)
    with caplog.at_level(logging.INFO, logger="project_hub.image_preview"):
        run(storage_bucket, doc)
    assert not has_object(s3_client, storage_bucket, preview)
    assert log_lines(caplog)[0]["message"] == "image preview skipped"


def test_truncated_png_gets_no_preview(s3_client: S3Client, storage_bucket: str) -> None:
    doc, preview = keys()
    full = image_bytes((300, 300), "PNG")
    put(s3_client, storage_bucket, doc, full[: len(full) // 2])
    run(storage_bucket, doc)
    assert not has_object(s3_client, storage_bucket, preview)


@pytest.mark.parametrize("side", [40, 100])
def test_decompression_bomb_gets_no_preview(
    monkeypatch: pytest.MonkeyPatch, s3_client: S3Client, storage_bucket: str, side: int
) -> None:
    monkeypatch.setattr(Image, "MAX_IMAGE_PIXELS", 1000)
    doc, preview = keys()
    put(s3_client, storage_bucket, doc, image_bytes((side, side), "PNG"))
    run(storage_bucket, doc)
    assert not has_object(s3_client, storage_bucket, preview)


def test_png_with_a_corrupt_chunk_gets_no_preview(
    s3_client: S3Client, storage_bucket: str, caplog: pytest.LogCaptureFixture
) -> None:
    doc, preview = keys()
    data = image_bytes((50, 50), "PNG")
    at = data.index(b"IDAT") - 4
    corrupt = struct.pack(">I", 5) + b"pHYs" + b"vvvvv" + struct.pack(">I", 0)
    put(s3_client, storage_bucket, doc, data[:at] + corrupt + data[at:])
    with caplog.at_level(logging.INFO, logger="project_hub.image_preview"):
        run(storage_bucket, doc)
    assert not has_object(s3_client, storage_bucket, preview)
    assert "ValueError" in log_lines(caplog)[0]["reason"]


@pytest.mark.filterwarnings("ignore:Corrupt EXIF data")
def test_jpeg_with_truncated_exif_does_not_raise(s3_client: S3Client, storage_bucket: str) -> None:
    doc, _ = keys()
    base = image_bytes((50, 50), "JPEG")
    exif = b"Exif\x00\x00II*\x00\x08\x00\x00\x00\x01\x00\x12\x01\x03\x00\x01\x00\x00\x00\x06"
    segment = b"\xff\xe1" + struct.pack(">H", len(exif) + 2) + exif
    put(s3_client, storage_bucket, doc, base[:2] + segment + base[2:])
    run(storage_bucket, doc)


@pytest.mark.parametrize(
    "error",
    [
        SyntaxError("broken PNG file"),
        ValueError("x"),
        struct.error("x"),
        ZeroDivisionError("x"),
        EOFError("x"),
    ],
    ids=lambda e: type(e).__name__,
)
def test_any_pillow_decode_error_gets_no_preview(
    monkeypatch: pytest.MonkeyPatch,
    s3_client: S3Client,
    storage_bucket: str,
    caplog: pytest.LogCaptureFixture,
    error: Exception,
) -> None:
    def broken(*args: Any, **kwargs: Any) -> None:
        raise error

    monkeypatch.setattr(ImageOps, "exif_transpose", broken)
    doc, preview = keys()
    put(s3_client, storage_bucket, doc, image_bytes((50, 50), "JPEG"))
    with caplog.at_level(logging.INFO, logger="project_hub.image_preview"):
        run(storage_bucket, doc)
    assert not has_object(s3_client, storage_bucket, preview)
    assert type(error).__name__ in log_lines(caplog)[0]["reason"]


def test_large_jpeg_gets_a_small_preview(s3_client: S3Client, storage_bucket: str) -> None:
    doc, preview = keys()
    put(s3_client, storage_bucket, doc, image_bytes((6000, 4000), "JPEG"))
    run(storage_bucket, doc)
    assert preview_of(s3_client, storage_bucket, preview).size == (512, 341)


def png_chunk(kind: bytes, data: bytes) -> bytes:
    return struct.pack(">I", len(data)) + kind + data + struct.pack(">I", zlib.crc32(kind + data))


def header_only_png(side: int) -> bytes:
    header = struct.pack(">IIBBBBB", side, side, 8, 2, 0, 0, 0)
    return b"\x89PNG\r\n\x1a\n" + png_chunk(b"IHDR", header) + png_chunk(b"IEND", b"")


@pytest.mark.parametrize(
    ("side", "refused_as_bomb"), [(6400, True), (6300, False)], ids=["41MP", "39.7MP"]
)
def test_pixel_guard_refuses_images_over_40_megapixels(
    s3_client: S3Client,
    storage_bucket: str,
    caplog: pytest.LogCaptureFixture,
    side: int,
    refused_as_bomb: bool,
) -> None:
    doc, preview = keys()
    put(s3_client, storage_bucket, doc, header_only_png(side))
    with caplog.at_level(logging.INFO, logger="project_hub.image_preview"):
        run(storage_bucket, doc)
    assert not has_object(s3_client, storage_bucket, preview)
    (line,) = log_lines(caplog)
    assert line["message"] == "image preview skipped"
    assert ("DecompressionBomb" in line["reason"]) is refused_as_bomb


def test_missing_object_is_skipped(
    s3_client: S3Client, storage_bucket: str, caplog: pytest.LogCaptureFixture
) -> None:
    doc, preview = keys()
    with caplog.at_level(logging.INFO, logger="project_hub.image_preview"):
        run(storage_bucket, doc)
    assert not has_object(s3_client, storage_bucket, preview)
    assert log_lines(caplog)[0]["message"] == "image preview skipped"


@pytest.mark.parametrize(
    "key",
    [
        "projects/not-a-uuid/documents/abc",
        f"projects/{uuid4()}/previews/abc.jpg",
        f"projects/{uuid4()}/documents/",
        f"projects/{uuid4()}/documents/a/b",
        f"other/{uuid4()}/documents/abc",
        "projects",
    ],
)
def test_keys_outside_documents_are_ignored(
    s3_client: S3Client, storage_bucket: str, key: str
) -> None:
    put(s3_client, storage_bucket, key, image_bytes((50, 50), "PNG"))
    before = s3_client.list_objects_v2(Bucket=storage_bucket)["KeyCount"]
    run(storage_bucket, key)
    run(storage_bucket, key, "Object Deleted")
    assert s3_client.list_objects_v2(Bucket=storage_bucket)["KeyCount"] == before


def test_write_to_previews_does_not_make_a_second_preview(
    s3_client: S3Client, storage_bucket: str
) -> None:
    doc, preview = keys()
    put(s3_client, storage_bucket, doc, image_bytes((50, 50), "PNG"))
    run(storage_bucket, doc)
    run(storage_bucket, preview)
    assert not has_object(s3_client, storage_bucket, preview + ".jpg")
    assert not has_object(s3_client, storage_bucket, preview.replace("previews", "documents"))


class FailingWrites:
    def __init__(self, client: Any) -> None:
        self._client = client

    def put_object(self, **kwargs: Any) -> None:
        raise ClientError({"Error": {"Code": "AccessDenied", "Message": "no"}}, "PutObject")

    def __getattr__(self, name: str) -> Any:
        return getattr(self._client, name)


def test_error_on_write_is_raised(
    monkeypatch: pytest.MonkeyPatch, s3_client: S3Client, storage_bucket: str
) -> None:
    doc, preview = keys()
    put(s3_client, storage_bucket, doc, image_bytes((50, 50), "PNG"))
    real = handler_module._s3_client  # pyright: ignore[reportPrivateUsage]
    monkeypatch.setattr(handler_module, "_s3_client", lambda: FailingWrites(real()))
    with pytest.raises(ClientError, match="AccessDenied"):
        run(storage_bucket, doc)
    assert not has_object(s3_client, storage_bucket, preview)


def test_error_on_read_other_than_missing_key_is_raised() -> None:
    doc, _ = keys()
    with pytest.raises(ClientError, match="NoSuchBucket"):
        run(f"no-such-bucket-{uuid4().hex}", doc)


def test_unreachable_storage_is_raised(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("APP_S3_ENDPOINT_URL", "http://127.0.0.1:1")
    monkeypatch.setenv("AWS_MAX_ATTEMPTS", "1")
    doc, _ = keys()
    with pytest.raises(Exception, match=r"127\.0\.0\.1"):
        run("whatever", doc)


def test_deleted_document_removes_its_preview(
    s3_client: S3Client, storage_bucket: str, caplog: pytest.LogCaptureFixture
) -> None:
    doc, preview = keys()
    _, other_preview = keys()
    put(s3_client, storage_bucket, preview, b"jpeg")
    put(s3_client, storage_bucket, other_preview, b"jpeg")
    with caplog.at_level(logging.INFO, logger="project_hub.image_preview"):
        run(storage_bucket, doc, "Object Deleted")
    assert not has_object(s3_client, storage_bucket, preview)
    assert has_object(s3_client, storage_bucket, other_preview)
    assert log_lines(caplog) == [
        {"message": "image preview deleted", "key": doc, "preview_key": preview}
    ]


def test_deleted_document_without_preview_is_not_an_error(storage_bucket: str) -> None:
    doc, _ = keys()
    run(storage_bucket, doc, "Object Deleted")


def test_unknown_event_shapes_are_ignored(storage_bucket: str) -> None:
    doc, _ = keys()
    assert handler({}, None) is None
    assert handler({"detail-type": "Object Created", "detail": {}}, None) is None
    assert handler(object_event(storage_bucket, doc, "Something Else"), None) is None
    assert (
        handler(
            {
                "detail-type": "Object Created",
                "detail": {"bucket": {"name": 1}, "object": {"key": 2}},
            },
            None,
        )
        is None
    )


def test_the_handler_imports_only_allowed_modules() -> None:
    import subprocess
    import sys

    code = (
        "import sys; import project_hub.image_preview.handler; "
        "bad = [m for m in ('project_hub.core', 'fastapi', 'pydantic', 'sqlalchemy', 'psycopg') "
        "if m in sys.modules]; print(bad)"
    )
    out = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True, check=True)
    assert out.stdout.strip() == "[]"
