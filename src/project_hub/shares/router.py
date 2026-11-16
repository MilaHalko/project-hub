from datetime import UTC, datetime
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query

from project_hub.auth.dependencies import CurrentUser
from project_hub.db.dependencies import get_uow
from project_hub.db.uow import UnitOfWork
from project_hub.shares import service
from project_hub.shares.dependencies import PublicUrl, ShareMailer
from project_hub.shares.schemas import ShareEmail, ShareResponse

router = APIRouter(tags=["shares"])


@router.get("/project/{project_id}/share")
async def share_project(
    project_id: UUID,
    user: CurrentUser,
    mailer: ShareMailer,
    public_url: PublicUrl,
    uow: Annotated[UnitOfWork, Depends(get_uow)],
    email: Annotated[ShareEmail, Query(alias="with")],
) -> ShareResponse:
    link = await service.share(
        uow, mailer, public_url, user, project_id, email, now=datetime.now(UTC)
    )
    return ShareResponse.from_link(link)
