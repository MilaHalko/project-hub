from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from project_hub.documents.entities import Document, NewDocument
from project_hub.documents.models import DocumentModel
from project_hub.users.models import UserModel


def _to_entity(model: DocumentModel, uploader_login: str | None) -> Document:
    return Document(
        id=model.id,
        project_id=model.project_id,
        name=model.name,
        content_type=model.content_type,
        size=model.size,
        storage_key=model.storage_key,
        uploaded_by=model.uploaded_by,
        uploader_login=uploader_login,
        created_at=model.created_at,
        updated_at=model.updated_at,
    )


class OrmDocumentRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def add(self, document: NewDocument) -> Document:
        model = DocumentModel(
            project_id=document.project_id,
            name=document.name,
            content_type=document.content_type,
            size=document.size,
            storage_key=document.storage_key,
            uploaded_by=document.uploaded_by,
        )
        async with self._session.begin_nested():
            self._session.add(model)
            await self._session.flush()
        login = await self._session.scalar(
            select(UserModel.login).where(UserModel.id == document.uploaded_by)
        )
        return _to_entity(model, login)

    async def get(self, document_id: UUID) -> Document | None:
        statement = (
            select(DocumentModel, UserModel.login)
            .outerjoin(UserModel, UserModel.id == DocumentModel.uploaded_by)
            .where(DocumentModel.id == document_id)
        )
        row = (await self._session.execute(statement)).one_or_none()
        return None if row is None else _to_entity(row[0], row[1])
