from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

from project_hub.projects.entities import ProjectAccess


@dataclass(frozen=True, slots=True)
class ShareLink:
    id: UUID
    project_id: UUID
    email: str
    expires_at: datetime


@dataclass(frozen=True, slots=True)
class JoinResult:
    access: ProjectAccess
    already_member: bool
