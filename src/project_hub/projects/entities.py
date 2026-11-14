from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from uuid import UUID


class ProjectRole(StrEnum):
    OWNER = "owner"
    PARTICIPANT = "participant"


def project_role(owner_id: UUID, user_id: UUID) -> ProjectRole:
    return ProjectRole.OWNER if owner_id == user_id else ProjectRole.PARTICIPANT


@dataclass(frozen=True, slots=True)
class NewProject:
    owner_id: UUID
    name: str
    description: str


@dataclass(frozen=True, slots=True)
class Project:
    id: UUID
    owner_id: UUID
    name: str
    description: str
    created_at: datetime
    updated_at: datetime


@dataclass(frozen=True, slots=True)
class ProjectAccess:
    project: Project
    owner_login: str
    role: ProjectRole


@dataclass(frozen=True, slots=True)
class ProjectMember:
    user_id: UUID
    login: str
    role: ProjectRole
    joined_at: datetime
