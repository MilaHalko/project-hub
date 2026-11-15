from collections.abc import Sequence
from uuid import UUID

from sqlalchemy import delete, func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from project_hub.documents.entities import Document, NewDocument, ReplacedFile
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

    async def replace_file(self, document_id: UUID, file: ReplacedFile) -> Document | None:
        statement = (
            update(DocumentModel)
            .where(DocumentModel.id == document_id)
            .values(
                name=file.name,
                content_type=file.content_type,
                size=file.size,
                storage_key=file.storage_key,
                uploaded_by=file.uploaded_by,
                updated_at=func.now(),
            )
            .returning(DocumentModel)
            .execution_options(populate_existing=True)
        )
        async with self._session.begin_nested():
            model = (await self._session.execute(statement)).scalar_one_or_none()
        if model is None:
            return None
        login = await self._session.scalar(
            select(UserModel.login).where(UserModel.id == file.uploaded_by)
        )
        return _to_entity(model, login)

    async def list_for_project(self, project_id: UUID) -> list[Document]:
        statement = (
            select(DocumentModel, UserModel.login)
            .outerjoin(UserModel, UserModel.id == DocumentModel.uploaded_by)
            .where(DocumentModel.project_id == project_id)
            .order_by(DocumentModel.created_at.desc(), DocumentModel.id.desc())
        )
        rows = (await self._session.execute(statement)).all()
        return [_to_entity(model, login) for model, login in rows]

    async def list_for_projects(self, project_ids: Sequence[UUID]) -> dict[UUID, list[Document]]:
        grouped: dict[UUID, list[Document]] = {project_id: [] for project_id in project_ids}
        if not grouped:
            return grouped
        statement = (
            select(DocumentModel, UserModel.login)
            .outerjoin(UserModel, UserModel.id == DocumentModel.uploaded_by)
            .where(DocumentModel.project_id.in_(list(grouped)))
            .order_by(DocumentModel.created_at.desc(), DocumentModel.id.desc())
        )
        for model, login in (await self._session.execute(statement)).all():
            grouped[model.project_id].append(_to_entity(model, login))
        return grouped

    async def delete(self, document_id: UUID) -> Document | None:
        statement = (
            delete(DocumentModel)
            .where(DocumentModel.id == document_id)
            .returning(DocumentModel)
            .execution_options(populate_existing=True)
        )
        model = (await self._session.execute(statement)).scalar_one_or_none()
        if model is None:
            return None
        login = await self._session.scalar(
            select(UserModel.login).where(UserModel.id == model.uploaded_by)
        )
        return _to_entity(model, login)

    async def storage_keys_for_project(self, project_id: UUID) -> list[str]:
        statement = select(DocumentModel.storage_key).where(DocumentModel.project_id == project_id)
        return list((await self._session.scalars(statement)).all())
