from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query, Response, status

from project_hub.auth.dependencies import CurrentUser
from project_hub.db.dependencies import get_uow
from project_hub.db.uow import UnitOfWork
from project_hub.projects import service
from project_hub.projects.entities import ProjectRole
from project_hub.projects.schemas import (
    InviteLogin,
    MemberResponse,
    ProjectIn,
    ProjectListItem,
    ProjectResponse,
)

router = APIRouter(tags=["projects"])


@router.post("/projects", status_code=status.HTTP_201_CREATED)
async def create_project(
    data: ProjectIn, user: CurrentUser, uow: Annotated[UnitOfWork, Depends(get_uow)]
) -> ProjectResponse:
    return ProjectResponse.from_access(await service.create_project(uow, user, data))


@router.get("/projects")
async def list_projects(
    user: CurrentUser,
    uow: Annotated[UnitOfWork, Depends(get_uow)],
    role: ProjectRole | None = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
    offset: Annotated[int, Query(ge=0, le=100_000)] = 0,
) -> list[ProjectListItem]:
    accesses = await service.list_projects(uow, user, role=role, limit=limit, offset=offset)
    return [ProjectListItem.from_access(access) for access in accesses]


@router.get("/project/{project_id}/info")
async def read_project(
    project_id: UUID, user: CurrentUser, uow: Annotated[UnitOfWork, Depends(get_uow)]
) -> ProjectResponse:
    return ProjectResponse.from_access(await service.get_project(uow, user, project_id))


@router.put("/project/{project_id}/info")
async def update_project(
    project_id: UUID,
    data: ProjectIn,
    user: CurrentUser,
    uow: Annotated[UnitOfWork, Depends(get_uow)],
) -> ProjectResponse:
    return ProjectResponse.from_access(await service.update_project(uow, user, project_id, data))


@router.delete(
    "/project/{project_id}", status_code=status.HTTP_204_NO_CONTENT, response_class=Response
)
async def delete_project(
    project_id: UUID, user: CurrentUser, uow: Annotated[UnitOfWork, Depends(get_uow)]
) -> None:
    await service.delete_project(uow, user, project_id)


@router.get("/project/{project_id}/members")
async def list_members(
    project_id: UUID, user: CurrentUser, uow: Annotated[UnitOfWork, Depends(get_uow)]
) -> list[MemberResponse]:
    members = await service.list_members(uow, user, project_id)
    return [MemberResponse.from_member(member) for member in members]


@router.post("/project/{project_id}/invite", status_code=status.HTTP_201_CREATED)
async def invite_member(
    project_id: UUID,
    caller: CurrentUser,
    uow: Annotated[UnitOfWork, Depends(get_uow)],
    login: Annotated[InviteLogin, Query(alias="user")],
) -> MemberResponse:
    member = await service.invite(uow, caller, project_id, login)
    return MemberResponse.from_member(member)


@router.delete(
    "/project/{project_id}/members/{user_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    response_class=Response,
)
async def remove_member(
    project_id: UUID,
    user_id: UUID,
    caller: CurrentUser,
    uow: Annotated[UnitOfWork, Depends(get_uow)],
) -> None:
    await service.remove_member(uow, caller, project_id, user_id)
