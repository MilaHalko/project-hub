import logging
from collections.abc import Sequence
from uuid import UUID

from project_hub.core.exceptions import NotFoundError
from project_hub.db.uow import UnitOfWork
from project_hub.documents.entities import Document, NewDocument, ReplacedFile, new_storage_key
from project_hub.documents.validation import ValidFile
from project_hub.projects.service import get_project
from project_hub.storage.files import FileStorage, discard_quietly
from project_hub.users.entities import User

logger = logging.getLogger(__name__)


def _log_event(event: str, user: User, project_id: UUID, document_id: UUID) -> None:
    logger.info(
        "%s login=%r user_id=%s project_id=%s document_id=%s",
        event,
        user.login,
        user.id,
        project_id,
        document_id,
        extra={
            "event": event,
            "login": user.login,
            "user_id": user.id,
            "project_id": project_id,
            "document_id": document_id,
        },
    )


async def upload_documents(
    uow: UnitOfWork,
    storage: FileStorage,
    user: User,
    project_id: UUID,
    files: Sequence[ValidFile],
) -> list[Document]:
    await get_project(uow, user, project_id)
    stored: list[tuple[str, ValidFile]] = []
    try:
        for file in files:
            key = new_storage_key(project_id)
            await storage.put(key, file.data, file.content_type)
            stored.append((key, file))
        documents = [
            await uow.documents.add(
                NewDocument(
                    project_id=project_id,
                    name=file.name,
                    content_type=file.content_type,
                    size=len(file.data),
                    storage_key=key,
                    uploaded_by=user.id,
                )
            )
            for key, file in stored
        ]
        await uow.projects.touch(project_id)
        await uow.commit()
    except Exception:
        await discard_quietly(storage, [key for key, _ in stored], project_id=project_id)
        raise
    for document in documents:
        _log_event("document uploaded", user, project_id, document.id)
    return documents


async def list_documents(uow: UnitOfWork, project_id: UUID) -> list[Document]:
    return await uow.documents.list_for_project(project_id)


async def documents_by_project(
    uow: UnitOfWork, project_ids: Sequence[UUID]
) -> dict[UUID, list[Document]]:
    return await uow.documents.list_for_projects(project_ids)


async def get_document(uow: UnitOfWork, user: User, document_id: UUID) -> Document:
    document = await uow.documents.get(document_id)
    if document is None:
        raise NotFoundError("Document not found")
    try:
        await get_project(uow, user, document.project_id)
    except NotFoundError as err:
        raise NotFoundError("Document not found") from err
    return document


async def download_document(storage: FileStorage, document: Document) -> bytes:
    return await storage.get(document.storage_key)


async def replace_document(
    uow: UnitOfWork,
    storage: FileStorage,
    user: User,
    document: Document,
    file: ValidFile,
) -> Document:
    new_key = new_storage_key(document.project_id)
    await storage.put(new_key, file.data, file.content_type)
    try:
        replaced = await uow.documents.replace_file(
            document.id,
            ReplacedFile(
                name=file.name,
                content_type=file.content_type,
                size=len(file.data),
                storage_key=new_key,
                uploaded_by=user.id,
            ),
        )
        if replaced is None:
            raise NotFoundError("Document not found")
        await uow.projects.touch(document.project_id)
        await uow.commit()
    except Exception:
        await discard_quietly(storage, [new_key], project_id=document.project_id)
        raise
    _log_event("document replaced", user, document.project_id, document.id)
    await discard_quietly(storage, [document.storage_key], project_id=document.project_id)
    return replaced


async def delete_document(
    uow: UnitOfWork, storage: FileStorage, user: User, document: Document
) -> None:
    deleted = await uow.documents.delete(document.id)
    if deleted is None:
        raise NotFoundError("Document not found")
    await uow.projects.touch(document.project_id)
    await uow.commit()
    _log_event("document deleted", user, document.project_id, document.id)
    await discard_quietly(storage, [deleted.storage_key], project_id=document.project_id)
