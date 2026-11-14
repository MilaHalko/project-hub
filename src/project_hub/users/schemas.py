from datetime import datetime
from uuid import UUID

from pydantic import BaseModel

from project_hub.users.entities import User


class UserResponse(BaseModel):
    id: UUID
    login: str
    created_at: datetime

    @classmethod
    def from_user(cls, user: User) -> "UserResponse":
        return cls(id=user.id, login=user.login, created_at=user.created_at)
