from project_hub.db.uow import UnitOfWork
from project_hub.users.entities import NewUser, User


async def create_user(uow: UnitOfWork, login: str, password_hash: str) -> User:
    """Add a user in the caller's transaction; the caller commits."""
    return await uow.users.add(NewUser(login=login, password_hash=password_hash))
