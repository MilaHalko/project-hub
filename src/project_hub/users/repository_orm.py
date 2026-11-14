from uuid import UUID

from sqlalchemy import select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from project_hub.core.exceptions import ConflictError
from project_hub.users.entities import NewUser, User
from project_hub.users.models import UserModel

_LOGIN_CONSTRAINT = "uq_users_login"


def _to_entity(model: UserModel) -> User:
    return User(
        id=model.id,
        login=model.login,
        password_hash=model.password_hash,
        created_at=model.created_at,
        token_version=model.token_version,
    )


def _is_login_conflict(error: IntegrityError) -> bool:
    diag = getattr(error.orig, "diag", None)
    return getattr(diag, "constraint_name", None) == _LOGIN_CONSTRAINT


class OrmUserRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def add(self, user: NewUser) -> User:
        model = UserModel(login=user.login, password_hash=user.password_hash)
        try:
            async with self._session.begin_nested():
                self._session.add(model)
                await self._session.flush()
        except IntegrityError as err:
            if _is_login_conflict(err):
                raise ConflictError(f"Login {user.login!r} is already taken") from err
            raise
        return _to_entity(model)

    async def get_by_id(self, user_id: UUID) -> User | None:
        model = await self._session.get(UserModel, user_id)
        return None if model is None else _to_entity(model)

    async def get_by_login(self, login: str) -> User | None:
        result = await self._session.execute(select(UserModel).where(UserModel.login == login))
        model = result.scalar_one_or_none()
        return None if model is None else _to_entity(model)

    async def increment_token_version(self, user_id: UUID) -> User | None:
        # Without populate_existing, a UserModel already loaded in this session keeps stale values.
        statement = (
            update(UserModel)
            .where(UserModel.id == user_id)
            .values(token_version=UserModel.token_version + 1)
            .returning(UserModel)
            .execution_options(populate_existing=True)
        )
        model = (await self._session.execute(statement)).scalar_one_or_none()
        return None if model is None else _to_entity(model)

    async def update_password(self, user_id: UUID, password_hash: str) -> User | None:
        statement = (
            update(UserModel)
            .where(UserModel.id == user_id)
            .values(password_hash=password_hash, token_version=UserModel.token_version + 1)
            .returning(UserModel)
            .execution_options(populate_existing=True)
        )
        model = (await self._session.execute(statement)).scalar_one_or_none()
        return None if model is None else _to_entity(model)
