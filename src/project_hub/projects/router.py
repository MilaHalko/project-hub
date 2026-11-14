from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, status

from project_hub.auth.dependencies import CurrentUser
from project_hub.db.dependencies import get_uow
from project_hub.db.uow import UnitOfWork
from project_hub.projects import service
from project_hub.projects.schemas import ProjectIn, ProjectResponse

router = APIRouter(tags=["projects"])


@router.post("/projects", status_code=status.HTTP_201_CREATED)
async def create_project(
    data: ProjectIn, user: CurrentUser, uow: Annotated[UnitOfWork, Depends(get_uow)]
) -> ProjectResponse:
    return ProjectResponse.from_access(await service.create_project(uow, user, data))


@router.get("/project/{project_id}/info")
async def read_project(
    project_id: UUID, user: CurrentUser, uow: Annotated[UnitOfWork, Depends(get_uow)]
) -> ProjectResponse:
    return ProjectResponse.from_access(await service.get_project(uow, user, project_id))
