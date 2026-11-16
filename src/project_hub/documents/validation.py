import io
import re
import unicodedata
import zipfile
from dataclasses import dataclass
from typing import Final

from starlette.datastructures import UploadFile

from project_hub.core.exceptions import PayloadTooLargeError, ValidationFailedError
from project_hub.documents.entities import DocumentType

_MAX_NAME_LENGTH: Final = 255
_FORBIDDEN_CATEGORIES: Final = frozenset({"Cc", "Cs"})
_MIB: Final = 1_048_576
_PATH_SEPARATORS: Final = re.compile(r"[/\\]")
_DOCX_MEMBERS: Final = frozenset({"[Content_Types].xml", "word/document.xml"})


@dataclass(frozen=True, slots=True)
class ValidFile:
    name: str
    content_type: str
    data: bytes


def clean_file_name(raw: str | None) -> str:
    name = _PATH_SEPARATORS.split(raw or "")[-1].strip()
    if not name:
        raise ValidationFailedError("File name is missing")
    if len(name) > _MAX_NAME_LENGTH:
        raise ValidationFailedError(f"File name is longer than {_MAX_NAME_LENGTH} characters")
    if any(unicodedata.category(ch) in _FORBIDDEN_CATEGORIES for ch in name):
        raise ValidationFailedError(f"File name {name!r} must not contain control characters")
    return name


def _zip_members(data: bytes) -> set[str] | None:
    try:
        with zipfile.ZipFile(io.BytesIO(data)) as archive:
            return set(archive.namelist())
    except (zipfile.BadZipFile, OSError, EOFError, ValueError):
        return None


def detect_type(data: bytes) -> DocumentType | None:
    if data.startswith(b"%PDF-"):
        return DocumentType.PDF
    members = _zip_members(data)
    if members is not None and members >= _DOCX_MEMBERS:
        return DocumentType.DOCX
    return None


def _type_from_extension(name: str) -> DocumentType | None:
    lowered = name.lower()
    for document_type in DocumentType:
        if lowered.endswith(document_type.extension):
            return document_type
    return None


def size_text(max_bytes: int) -> str:
    if max_bytes % _MIB == 0:
        return f"{max_bytes // _MIB} MB"
    return f"{max_bytes} bytes"


async def read_valid_file(upload: UploadFile, max_bytes: int) -> ValidFile:
    name = clean_file_name(upload.filename)
    expected = _type_from_extension(name)
    if expected is None:
        raise ValidationFailedError(f"{name}: only pdf and docx documents are allowed")
    data = await upload.read(max_bytes + 1)
    if len(data) > max_bytes:
        raise PayloadTooLargeError(f"{name}: file is larger than {size_text(max_bytes)}")
    if not data:
        raise ValidationFailedError(f"{name}: file is empty")
    if detect_type(data) is not expected:
        raise ValidationFailedError(f"{name}: content is not a valid {expected.value}")
    return ValidFile(name=name, content_type=expected.content_type, data=data)
