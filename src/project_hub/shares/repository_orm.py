from datetime import datetime
from uuid import UUID

from sqlalchemy import delete, func, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from project_hub.core.exceptions import NotFoundError
from project_hub.shares.entities import ShareLink
from project_hub.shares.models import ShareModel

_SHARE_PROJECT_FK = "fk_project_shares_project_id_projects"
_SHARE_ADDRESS_CONSTRAINT = "uq_project_shares_project_id_email"


def _violated_constraint(error: IntegrityError) -> str | None:
    diag = getattr(error.orig, "diag", None)
    name: str | None = getattr(diag, "constraint_name", None)
    return name


class OrmShareRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def delete_expired(self, project_id: UUID, now: datetime) -> None:
        await self._session.execute(
            delete(ShareModel).where(
                ShareModel.project_id == project_id, ShareModel.expires_at <= now
            )
        )

    async def count_pending(self, project_id: UUID, now: datetime, *, except_email: str) -> int:
        statement = (
            select(func.count())
            .select_from(ShareModel)
            .where(
                ShareModel.project_id == project_id,
                ShareModel.expires_at > now,
                ShareModel.email != except_email,
            )
        )
        return (await self._session.execute(statement)).scalar_one()

    async def put(
        self, project_id: UUID, email: str, token_hash: str, expires_at: datetime
    ) -> None:
        values = insert(ShareModel).values(
            project_id=project_id, email=email, token_hash=token_hash, expires_at=expires_at
        )
        statement = values.on_conflict_do_update(
            constraint=_SHARE_ADDRESS_CONSTRAINT,
            set_={
                # A new id, so a join that looked up the replaced link cannot claim this one.
                "id": func.gen_random_uuid(),
                "token_hash": values.excluded.token_hash,
                "expires_at": values.excluded.expires_at,
                "created_at": func.now(),
            },
        )
        try:
            async with self._session.begin_nested():
                await self._session.execute(statement)
        except IntegrityError as err:
            if _violated_constraint(err) == _SHARE_PROJECT_FK:
                raise NotFoundError("Project not found") from err
            raise

    async def find_pending(self, token_hash: str, now: datetime) -> ShareLink | None:
        statement = select(
            ShareModel.id, ShareModel.project_id, ShareModel.email, ShareModel.expires_at
        ).where(ShareModel.token_hash == token_hash, ShareModel.expires_at > now)
        row = (await self._session.execute(statement)).one_or_none()
        if row is None:
            return None
        return ShareLink(
            id=row.id, project_id=row.project_id, email=row.email, expires_at=row.expires_at
        )

    async def claim(self, share_id: UUID) -> bool:
        statement = delete(ShareModel).where(ShareModel.id == share_id).returning(ShareModel.id)
        return (await self._session.execute(statement)).scalar_one_or_none() is not None
