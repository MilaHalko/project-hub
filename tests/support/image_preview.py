from io import BytesIO
from typing import Any

from PIL import Image

from tests.support.storage_usage import eventbridge_event


def object_event(bucket: str, key: str, detail_type: str = "Object Created") -> dict[str, Any]:
    return eventbridge_event(bucket, key, detail_type)


def image_bytes(
    size: tuple[int, int],
    fmt: str = "PNG",
    mode: str = "RGB",
    color: Any = (200, 30, 30),
    orientation: int | None = None,
) -> bytes:
    image = Image.new(mode, size, color)
    out = BytesIO()
    if orientation is None:
        image.save(out, format=fmt)
    else:
        exif = Image.Exif()
        exif[0x0112] = orientation
        image.save(out, format=fmt, exif=exif)
    return out.getvalue()
