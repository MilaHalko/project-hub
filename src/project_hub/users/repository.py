from typing import Protocol
from uuid import UUID

from project_hub.users.entities import NewUser, User


class UserRepository(Protocol):
    async def add(self, user: NewUser) -> User:
        """Store a new user; raise ``ConflictError`` if the login is already taken."""
        ...

    async def get_by_id(self, user_id: UUID) -> User | None: ...

    async def get_by_login(self, login: str) -> User | None: ...
