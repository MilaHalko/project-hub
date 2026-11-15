import unicodedata
from collections.abc import Sequence
from datetime import datetime
from typing import Annotated, Self
from uuid import UUID

from pydantic import AfterValidator, BaseModel, StringConstraints

from project_hub.core.text import reject_nul
from project_hub.documents.entities import Document
from project_hub.documents.schemas import DocumentResponse
from project_hub.projects.entities import ProjectAccess, ProjectMember, ProjectRole


def _reject_control_characters(value: str) -> str:
    if any(unicodedata.category(ch) == "Cc" for ch in value):
        raise ValueError("Name must not contain control characters")
    return value


ProjectName = Annotated[
    str,
    StringConstraints(strip_whitespace=True, min_length=1, max_length=100),
    AfterValidator(_reject_control_characters),
]
ProjectDescription = Annotated[str, StringConstraints(max_length=2000), AfterValidator(reject_nul)]
InviteLogin = Annotated[
    str, StringConstraints(min_length=1, max_length=32), AfterValidator(reject_nul)
]


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
    documents: list[DocumentResponse] = []

    @classmethod
    def from_access(cls, access: ProjectAccess, documents: Sequence[Document] = ()) -> Self:
        project = access.project
        return cls(
            id=project.id,
            name=project.name,
            description=project.description,
            owner=OwnerResponse(id=project.owner_id, login=access.owner_login),
            my_role=access.role,
            created_at=project.created_at,
            updated_at=project.updated_at,
            documents=[DocumentResponse.from_document(document) for document in documents],
        )


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
