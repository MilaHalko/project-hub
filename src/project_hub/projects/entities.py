from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from uuid import UUID


class ProjectRole(StrEnum):
    OWNER = "owner"
    PARTICIPANT = "participant"


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
