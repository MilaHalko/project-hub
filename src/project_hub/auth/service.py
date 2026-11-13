from project_hub.auth.passwords import PasswordHasher
from project_hub.auth.schemas import RegisterRequest
from project_hub.db.uow import UnitOfWork
from project_hub.users import service as users_service
from project_hub.users.entities import User


async def register(uow: UnitOfWork, hasher: PasswordHasher, data: RegisterRequest) -> User:
    password_hash = await hasher.hash(data.password.get_secret_value())
    user = await users_service.create_user(uow, data.login, password_hash)
    await uow.commit()
    return user
