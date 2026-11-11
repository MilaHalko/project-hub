from types import TracebackType
from typing import Protocol, Self

from project_hub.users.repository import UserRepository


class UnitOfWork(Protocol):
    """One transaction scope exposing the repositories that share it.

    A Unit of Work is a single transaction and is not for concurrent use by several
    tasks. Leaving it without ``commit()`` rolls the transaction back. After a
    repository method raises (for example ``ConflictError``) it stays usable.
    """

    users: UserRepository

    async def commit(self) -> None: ...

    async def rollback(self) -> None: ...

    async def __aenter__(self) -> Self: ...

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None: ...
