from dataclasses import dataclass
from datetime import datetime
from uuid import UUID


@dataclass(frozen=True, slots=True)
class ShareLink:
    id: UUID
    project_id: UUID
    email: str
    expires_at: datetime
