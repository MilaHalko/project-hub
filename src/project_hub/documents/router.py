from typing import Annotated, Any
from urllib.parse import quote
from uuid import UUID

from fastapi import APIRouter, Depends, Request, Response, status

from project_hub.auth.dependencies import CurrentUser
from project_hub.core.config import Settings
from project_hub.db.dependencies import get_uow
from project_hub.db.uow import UnitOfWork
from project_hub.documents import service
from project_hub.documents.dependencies import AccessibleDocument, AccessibleProject
from project_hub.documents.forms import read_uploads
from project_hub.documents.schemas import DocumentResponse
from project_hub.storage.dependencies import Storage


def content_disposition(name: str) -> str:
    ascii_name = "".join(
        char if char.isascii() and char.isprintable() and char not in '"\\;' else "_"
        for char in name
    )
    return f"attachment; filename=\"{ascii_name}\"; filename*=UTF-8''{quote(name, safe='')}"


router = APIRouter(tags=["documents"])

_FILE_BODY: dict[str, Any] = {
    "requestBody": {
        "required": True,
        "content": {
            "multipart/form-data": {
                "schema": {
                    "type": "object",
                    "required": ["file"],
                    "properties": {"file": {"type": "string", "format": "binary"}},
                }
            }
        },
    }
}

_FILES_BODY: dict[str, Any] = {
    "requestBody": {
        "required": True,
        "content": {
            "multipart/form-data": {
                "schema": {
                    "type": "object",
                    "required": ["files"],
                    "properties": {
                        "files": {
                            "type": "array",
                            "items": {"type": "string", "format": "binary"},
                        }
                    },
                }
            }
        },
    }
}


@router.post(
    "/project/{project_id}/documents",
    status_code=status.HTTP_201_CREATED,
    openapi_extra=_FILES_BODY,
)
async def upload_documents(
    project_id: UUID,
    request: Request,
    project: AccessibleProject,
    user: CurrentUser,
    uow: Annotated[UnitOfWork, Depends(get_uow)],
    storage: Storage,
) -> list[DocumentResponse]:
    settings: Settings = request.app.state.settings
    files = await read_uploads(request, settings, "files", exactly_one=False)
    documents = await service.upload_documents(
        uow, storage, user, project.project.id, files, limit_bytes=settings.project_max_bytes
    )
    return [DocumentResponse.from_document(document) for document in documents]


@router.get("/project/{project_id}/documents")
async def list_documents(
    project_id: UUID,
    project: AccessibleProject,
    user: CurrentUser,
    uow: Annotated[UnitOfWork, Depends(get_uow)],
) -> list[DocumentResponse]:
    documents = await service.list_documents(uow, project.project.id)
    return [DocumentResponse.from_document(document) for document in documents]


@router.get("/document/{document_id}")
async def download_document(document: AccessibleDocument, storage: Storage) -> Response:
    data = await service.download_document(storage, document)
    return Response(
        content=data,
        media_type=document.content_type,
        headers={
            "Content-Disposition": content_disposition(document.name),
            "X-Content-Type-Options": "nosniff",
            "Cache-Control": "private, no-store",
        },
    )


@router.put("/document/{document_id}", openapi_extra=_FILE_BODY)
async def replace_document(
    document_id: UUID,
    request: Request,
    document: AccessibleDocument,
    user: CurrentUser,
    uow: Annotated[UnitOfWork, Depends(get_uow)],
    storage: Storage,
) -> DocumentResponse:
    settings: Settings = request.app.state.settings
    (file,) = await read_uploads(request, settings, "file", exactly_one=True)
    replaced = await service.replace_document(
        uow, storage, user, document, file, limit_bytes=settings.project_max_bytes
    )
    return DocumentResponse.from_document(replaced)


@router.delete(
    "/document/{document_id}", status_code=status.HTTP_204_NO_CONTENT, response_class=Response
)
async def delete_document(
    document: AccessibleDocument,
    user: CurrentUser,
    uow: Annotated[UnitOfWork, Depends(get_uow)],
    storage: Storage,
) -> None:
    await service.delete_document(uow, storage, user, document)
