from typing import Protocol
from uuid import UUID

from project_hub.users.entities import NewUser, User


class UserRepository(Protocol):
    async def add(self, user: NewUser) -> User:
        """Store a new user; raise ``ConflictError`` if the login is already taken."""
        ...

    async def get_by_id(self, user_id: UUID) -> User | None: ...

    async def get_by_login(self, login: str) -> User | None: ...

    async def increment_token_version(self, user_id: UUID) -> User | None:
        """Add one to the user's ``token_version`` atomically; ``None`` for an unknown id."""
        ...

    async def update_password(self, user_id: UUID, password_hash: str) -> User | None:
        """Set the hash and add one to ``token_version`` in one statement; ``None`` if unknown."""
        ...
