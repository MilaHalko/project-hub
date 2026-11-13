from dataclasses import dataclass
from datetime import datetime
from uuid import UUID


@dataclass(frozen=True, slots=True)
class NewUser:
    login: str
    password_hash: str


@dataclass(frozen=True, slots=True)
class User:
    id: UUID
    login: str
    password_hash: str
    created_at: datetime
    token_version: int
