from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from typing import Final
from uuid import UUID, uuid4

PDF_CONTENT_TYPE: Final = "application/pdf"
DOCX_CONTENT_TYPE: Final = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"


class DocumentType(StrEnum):
    PDF = "pdf"
    DOCX = "docx"

    @property
    def extension(self) -> str:
        return f".{self.value}"

    @property
    def content_type(self) -> str:
        return PDF_CONTENT_TYPE if self is DocumentType.PDF else DOCX_CONTENT_TYPE


@dataclass(frozen=True, slots=True)
class NewDocument:
    project_id: UUID
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
