from typing import Annotated, Any
from uuid import UUID

from fastapi import APIRouter, Depends, Request, status

from project_hub.auth.dependencies import CurrentUser
from project_hub.core.config import Settings
from project_hub.db.dependencies import get_uow
from project_hub.db.uow import UnitOfWork
from project_hub.documents import service
from project_hub.documents.dependencies import AccessibleProject
from project_hub.documents.forms import read_uploads
from project_hub.documents.schemas import DocumentResponse
from project_hub.storage.dependencies import Storage

router = APIRouter(tags=["documents"])

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
    documents = await service.upload_documents(uow, storage, user, project.project.id, files)
    return [DocumentResponse.from_document(document) for document in documents]
