from typing import Annotated
from uuid import UUID

from fastapi import Depends

from project_hub.auth.dependencies import CurrentUser
from project_hub.db.dependencies import get_uow
from project_hub.db.uow import UnitOfWork
from project_hub.documents.entities import Document
from project_hub.documents.service import get_document
from project_hub.projects.entities import ProjectAccess
from project_hub.projects.service import get_project


async def get_accessible_project(
    project_id: UUID, user: CurrentUser, uow: Annotated[UnitOfWork, Depends(get_uow)]
) -> ProjectAccess:
    return await get_project(uow, user, project_id)


AccessibleProject = Annotated[ProjectAccess, Depends(get_accessible_project)]


async def get_accessible_document(
    document_id: UUID, user: CurrentUser, uow: Annotated[UnitOfWork, Depends(get_uow)]
) -> Document:
    return await get_document(uow, user, document_id)


AccessibleDocument = Annotated[Document, Depends(get_accessible_document)]
