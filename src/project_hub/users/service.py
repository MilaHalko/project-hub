from uuid import UUID

from project_hub.db.uow import UnitOfWork
from project_hub.users.entities import NewUser, User


async def create_user(uow: UnitOfWork, login: str, password_hash: str) -> User:
    """Add a user in the caller's transaction; the caller commits."""
    return await uow.users.add(NewUser(login=login, password_hash=password_hash))


async def get_user_by_login(uow: UnitOfWork, login: str) -> User | None:
    return await uow.users.get_by_login(login)


async def get_user(uow: UnitOfWork, user_id: UUID) -> User | None:
    return await uow.users.get_by_id(user_id)
