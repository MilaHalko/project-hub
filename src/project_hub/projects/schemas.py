import unicodedata
from datetime import datetime
from typing import Annotated, Any, Self
from uuid import UUID

from pydantic import AfterValidator, BaseModel, StringConstraints

from project_hub.projects.entities import ProjectAccess, ProjectMember, ProjectRole


def _reject_control_characters(value: str) -> str:
    if any(unicodedata.category(ch) == "Cc" for ch in value):
        raise ValueError("Name must not contain control characters")
    return value


def _reject_nul(value: str) -> str:
    if "\x00" in value:
        raise ValueError("Description must not contain NUL characters")
    return value


ProjectName = Annotated[
    str,
    StringConstraints(strip_whitespace=True, min_length=1, max_length=100),
    AfterValidator(_reject_control_characters),
]
ProjectDescription = Annotated[str, StringConstraints(max_length=2000), AfterValidator(_reject_nul)]


class ProjectIn(BaseModel):
    name: ProjectName
    description: ProjectDescription = ""


class OwnerResponse(BaseModel):
    id: UUID
    login: str


class ProjectResponse(BaseModel):
    id: UUID
    name: str
    description: str
    owner: OwnerResponse
    my_role: ProjectRole
    created_at: datetime
    updated_at: datetime

    @classmethod
    def from_access(cls, access: ProjectAccess) -> Self:
        project = access.project
        return cls(
            id=project.id,
            name=project.name,
            description=project.description,
            owner=OwnerResponse(id=project.owner_id, login=access.owner_login),
            my_role=access.role,
            created_at=project.created_at,
            updated_at=project.updated_at,
        )


class ProjectListItem(ProjectResponse):
    documents: list[dict[str, Any]] = []


class MemberResponse(BaseModel):
    id: UUID
    login: str
    role: ProjectRole
    joined_at: datetime

    @classmethod
    def from_member(cls, member: ProjectMember) -> Self:
        return cls(
            id=member.user_id, login=member.login, role=member.role, joined_at=member.joined_at
        )
