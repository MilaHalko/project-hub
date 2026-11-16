from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from typing import Final
from uuid import UUID, uuid4

PDF_CONTENT_TYPE: Final = "application/pdf"
DOCX_CONTENT_TYPE: Final = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
JPEG_CONTENT_TYPE: Final = "image/jpeg"
PNG_CONTENT_TYPE: Final = "image/png"


class DocumentType(StrEnum):
    PDF = "pdf"
    DOCX = "docx"
    JPEG = "jpeg"
    PNG = "png"

    @property
    def extension(self) -> str:
        return f".{self.value}"

    @property
    def extensions(self) -> tuple[str, ...]:
        if self is DocumentType.JPEG:
            return (".jpg", ".jpeg")
        return (self.extension,)

    @property
    def content_type(self) -> str:
        return _CONTENT_TYPES[self]


_CONTENT_TYPES: Final = {
    DocumentType.PDF: PDF_CONTENT_TYPE,
    DocumentType.DOCX: DOCX_CONTENT_TYPE,
    DocumentType.JPEG: JPEG_CONTENT_TYPE,
    DocumentType.PNG: PNG_CONTENT_TYPE,
}


@dataclass(frozen=True, slots=True)
class NewDocument:
    project_id: UUID
    name: str
    content_type: str
    size: int
    storage_key: str
    uploaded_by: UUID


@dataclass(frozen=True, slots=True)
class ReplacedFile:
    name: str
    content_type: str
    size: int
    storage_key: str
    uploaded_by: UUID


@dataclass(frozen=True, slots=True)
class Document:
    id: UUID
    project_id: UUID
    name: str
    content_type: str
    size: int
    storage_key: str
    uploaded_by: UUID | None
    uploader_login: str | None
    created_at: datetime
    updated_at: datetime


def new_storage_key(project_id: UUID) -> str:
    return f"projects/{project_id}/documents/{uuid4().hex}"
