from datetime import datetime
from typing import Self
from uuid import UUID

from pydantic import BaseModel

from project_hub.documents.entities import Document


class UploaderResponse(BaseModel):
    id: UUID
    login: str


class DocumentResponse(BaseModel):
    id: UUID
    project_id: UUID
    name: str
    content_type: str
    size: int
    uploaded_by: UploaderResponse | None
    created_at: datetime
    updated_at: datetime

    @classmethod
    def from_document(cls, document: Document) -> Self:
        uploader = (
            None
            if document.uploaded_by is None or document.uploader_login is None
            else UploaderResponse(id=document.uploaded_by, login=document.uploader_login)
        )
        return cls(
            id=document.id,
            project_id=document.project_id,
            name=document.name,
            content_type=document.content_type,
            size=document.size,
            uploaded_by=uploader,
            created_at=document.created_at,
            updated_at=document.updated_at,
        )
