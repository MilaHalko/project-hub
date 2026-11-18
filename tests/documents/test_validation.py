import io

import pytest
from starlette.datastructures import Headers, UploadFile

from project_hub.core.exceptions import PayloadTooLargeError, ValidationFailedError
from project_hub.documents.entities import DOCX_CONTENT_TYPE, PDF_CONTENT_TYPE, DocumentType
from project_hub.documents.validation import (
    ValidFile,
    clean_file_name,
    detect_type,
    read_valid_file,
)
from tests.support.documents import JPEG_BYTES, PNG_BYTES, docx_bytes, pdf_bytes, zip_bytes

pytestmark = pytest.mark.anyio

TEN_MB = 10_485_760


class _CountingReader(io.BytesIO):
    def __init__(self, data: bytes) -> None:
        super().__init__(data)
        self.bytes_read = 0

    def read(self, size: int | None = -1, /) -> bytes:
        chunk = super().read(size)
        self.bytes_read += len(chunk)
        return chunk


def _upload(name: str | None, data: bytes, content_type: str = "text/plain") -> UploadFile:
    return UploadFile(
        io.BytesIO(data), filename=name, headers=Headers({"content-type": content_type})
    )


@pytest.mark.parametrize(
    ("raw", "cleaned"),
    [
        pytest.param("../../etc/x.pdf", "x.pdf", id="posix-path"),
        pytest.param("C:\\tmp\\x.pdf", "x.pdf", id="windows-path"),
        pytest.param("  a.pdf ", "a.pdf", id="whitespace"),
        pytest.param("диплом.pdf", "диплом.pdf", id="unicode"),
        pytest.param("x" * 251 + ".pdf", "x" * 251 + ".pdf", id="255-chars"),
    ],
)
def test_clean_file_name_keeps_last_part(raw: str, cleaned: str) -> None:
    assert clean_file_name(raw) == cleaned


@pytest.mark.parametrize("raw", [None, "", "dir/", "  ", "a/  "])
def test_clean_file_name_missing(raw: str | None) -> None:
    with pytest.raises(ValidationFailedError) as exc_info:
        clean_file_name(raw)
    assert exc_info.value.message == "File name is missing"


@pytest.mark.parametrize(
    "raw",
    [
        pytest.param("x" * 252 + ".pdf", id="256-chars"),
        pytest.param("a\nb.pdf", id="newline"),
        pytest.param("a\x07b.pdf", id="bell"),
        pytest.param("a\x7fb.pdf", id="delete"),
        pytest.param("\ud83d.pdf", id="lone-surrogate"),
    ],
)
def test_clean_file_name_rejects_long_or_control(raw: str) -> None:
    with pytest.raises(ValidationFailedError):
        clean_file_name(raw)


def test_clean_file_name_does_not_echo_a_name_that_is_too_long() -> None:
    with pytest.raises(ValidationFailedError) as exc_info:
        clean_file_name("x" * 300 + "\x07.pdf")
    assert exc_info.value.message == "File name is longer than 255 characters"


@pytest.mark.parametrize(
    ("data", "expected"),
    [
        pytest.param(pdf_bytes(), DocumentType.PDF, id="pdf"),
        pytest.param(docx_bytes(), DocumentType.DOCX, id="docx"),
        pytest.param(PNG_BYTES, DocumentType.PNG, id="png"),
        pytest.param(b"GIF89a", None, id="gif"),
        pytest.param(b"PK\x03\x04garbage", None, id="broken-zip"),
        pytest.param(zip_bytes(**{"[Content_Types].xml": "<Types/>"}), None, id="zip-no-word"),
        pytest.param(zip_bytes(**{"word/document.xml": "<d/>"}), None, id="zip-no-types"),
        pytest.param(b"", None, id="empty"),
    ],
)
def test_detect_type(data: bytes, expected: DocumentType | None) -> None:
    assert detect_type(data) is expected


def test_document_type_extension_and_content_type() -> None:
    assert (DocumentType.PDF.extension, DocumentType.PDF.content_type) == (
        ".pdf",
        "application/pdf",
    )
    assert (DocumentType.DOCX.extension, DocumentType.DOCX.content_type) == (
        ".docx",
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    )


async def test_read_valid_pdf_uses_canonical_content_type() -> None:
    data = pdf_bytes()

    valid = await read_valid_file(_upload("thesis.pdf", data), TEN_MB)

    assert valid == ValidFile(name="thesis.pdf", content_type=PDF_CONTENT_TYPE, data=data)


async def test_read_valid_docx_upper_case_extension_keeps_name() -> None:
    data = docx_bytes()

    valid = await read_valid_file(_upload("../THESIS.DOCX", data, "application/pdf"), TEN_MB)

    assert valid == ValidFile(name="THESIS.DOCX", content_type=DOCX_CONTENT_TYPE, data=data)


async def test_read_valid_file_rejects_other_extension() -> None:
    with pytest.raises(ValidationFailedError) as exc_info:
        await read_valid_file(_upload("photo.gif", PNG_BYTES), TEN_MB)
    assert exc_info.value.message == "photo.gif: only pdf, docx, jpg and png documents are allowed"


@pytest.mark.parametrize(
    ("max_bytes", "message"),
    [
        pytest.param(TEN_MB, "big.pdf: file is larger than 10 MB", id="whole-mib"),
        pytest.param(100, "big.pdf: file is larger than 100 bytes", id="bytes"),
        pytest.param(1_048_577, "big.pdf: file is larger than 1048577 bytes", id="not-whole"),
    ],
)
async def test_read_valid_file_too_large(max_bytes: int, message: str) -> None:
    data = pdf_bytes() + b"\0" * max_bytes

    with pytest.raises(PayloadTooLargeError) as exc_info:
        await read_valid_file(_upload("big.pdf", data), max_bytes)
    assert exc_info.value.message == message


async def test_read_valid_file_accepts_exactly_max_bytes() -> None:
    data = pdf_bytes().ljust(100, b"\0")

    valid = await read_valid_file(_upload("full.pdf", data), 100)

    assert valid.data == data


async def test_read_valid_file_reads_at_most_max_bytes_plus_one() -> None:
    reader = _CountingReader(pdf_bytes() + b"\0" * 1000)
    upload = UploadFile(reader, filename="big.pdf")

    with pytest.raises(PayloadTooLargeError):
        await read_valid_file(upload, 100)
    assert reader.bytes_read == 101


async def test_read_valid_file_rejects_empty() -> None:
    with pytest.raises(ValidationFailedError) as exc_info:
        await read_valid_file(_upload("e.pdf", b""), TEN_MB)
    assert exc_info.value.message == "e.pdf: file is empty"


@pytest.mark.parametrize(
    ("name", "data", "message"),
    [
        pytest.param(
            "x.docx", pdf_bytes(), "x.docx: content is not a valid docx", id="pdf-as-docx"
        ),
        pytest.param("x.pdf", docx_bytes(), "x.pdf: content is not a valid pdf", id="docx-as-pdf"),
        pytest.param("x.pdf", PNG_BYTES, "x.pdf: content is not a valid pdf", id="png-as-pdf"),
    ],
)
async def test_read_valid_file_content_must_match_extension(
    name: str, data: bytes, message: str
) -> None:
    with pytest.raises(ValidationFailedError) as exc_info:
        await read_valid_file(_upload(name, data), TEN_MB)
    assert exc_info.value.message == message


async def test_read_valid_file_checks_name_first() -> None:
    with pytest.raises(ValidationFailedError) as exc_info:
        await read_valid_file(_upload(None, b""), TEN_MB)
    assert exc_info.value.message == "File name is missing"


@pytest.mark.parametrize(
    ("data", "expected"),
    [
        pytest.param(JPEG_BYTES, DocumentType.JPEG, id="jpeg"),
        pytest.param(PNG_BYTES, DocumentType.PNG, id="png"),
        pytest.param(b"\xff\xd8\x00", None, id="short-jpeg-signature"),
        pytest.param(b"\x89PNG\r\n", None, id="short-png-signature"),
    ],
)
def test_detect_type_images(data: bytes, expected: DocumentType | None) -> None:
    assert detect_type(data) is expected


@pytest.mark.parametrize(
    ("name", "data", "content_type"),
    [
        pytest.param("a.jpg", JPEG_BYTES, "image/jpeg", id="jpg"),
        pytest.param("a.jpeg", JPEG_BYTES, "image/jpeg", id="jpeg-alias"),
        pytest.param("A.JPG", JPEG_BYTES, "image/jpeg", id="upper-jpg"),
        pytest.param("a.png", PNG_BYTES, "image/png", id="png"),
        pytest.param("A.PNG", PNG_BYTES, "image/png", id="upper-png"),
    ],
)
async def test_read_valid_image(name: str, data: bytes, content_type: str) -> None:
    valid = await read_valid_file(_upload(name, data, "application/octet-stream"), TEN_MB)

    assert valid == ValidFile(name=name, content_type=content_type, data=data)


@pytest.mark.parametrize(
    ("name", "data", "message"),
    [
        pytest.param("a.png", JPEG_BYTES, "a.png: content is not a valid png", id="jpeg-as-png"),
        pytest.param("a.png", pdf_bytes(), "a.png: content is not a valid png", id="pdf-as-png"),
        pytest.param("a.jpg", PNG_BYTES, "a.jpg: content is not a valid jpeg", id="png-as-jpg"),
        pytest.param(
            "a.jpeg", pdf_bytes(), "a.jpeg: content is not a valid jpeg", id="pdf-as-jpeg"
        ),
        pytest.param("a.pdf", JPEG_BYTES, "a.pdf: content is not a valid pdf", id="jpeg-as-pdf"),
    ],
)
async def test_read_valid_image_rejects_wrong_content(name: str, data: bytes, message: str) -> None:
    with pytest.raises(ValidationFailedError) as exc_info:
        await read_valid_file(_upload(name, data), TEN_MB)
    assert exc_info.value.message == message


async def test_read_valid_file_rejects_gif_with_new_message() -> None:
    with pytest.raises(ValidationFailedError) as exc_info:
        await read_valid_file(_upload("a.gif", b"GIF89a"), TEN_MB)
    assert exc_info.value.message == "a.gif: only pdf, docx, jpg and png documents are allowed"
