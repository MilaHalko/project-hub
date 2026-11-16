import logging
from datetime import UTC, datetime, timedelta
from uuid import UUID

from project_hub.core.exceptions import (
    ConflictError,
    NotFoundError,
    PermissionDeniedError,
    ServiceUnavailableError,
    TooManyRequestsError,
)
from project_hub.db.uow import UnitOfWork
from project_hub.mail.mailer import MailDeliveryError, Mailer, OutgoingMail
from project_hub.projects.entities import ProjectAccess, ProjectRole
from project_hub.projects.service import get_project
from project_hub.shares.entities import JoinResult, ShareLink
from project_hub.shares.tokens import hash_token, new_token
from project_hub.users.entities import User

SHARE_TTL = timedelta(days=7)
MAX_PENDING_SHARES = 10
SUBJECT = "You are invited to a project on Project Hub"
_INVALID_LINK = "Invite link is invalid or expired"

logger = logging.getLogger(__name__)


def _log_event(event: str, user: User, project_id: UUID, email: str) -> None:
    logger.info(
        "%s login=%r user_id=%s project_id=%s email=%r",
        event,
        user.login,
        user.id,
        project_id,
        email,
        extra={
            "event": event,
            "login": user.login,
            "user_id": user.id,
            "project_id": project_id,
            "email": email,
        },
    )


def _invitation(sharer: str, project_name: str, link: str, expires_at: datetime) -> str:
    expiry = expires_at.astimezone(UTC).strftime("%Y-%m-%d %H:%M")
    return (
        f'@{sharer} invited you to the project "{project_name}" on Project Hub.\n'
        "\n"
        "Open this link and sign in to join:\n"
        f"{link}\n"
        "\n"
        f"The link works once and expires at {expiry} UTC.\n"
    )


async def share(
    uow: UnitOfWork,
    mailer: Mailer,
    public_url: str,
    user: User,
    project_id: UUID,
    email: str,
    *,
    now: datetime,
) -> ShareLink:
    access = await get_project(uow, user, project_id)
    if access.role is ProjectRole.PARTICIPANT:
        raise PermissionDeniedError("Only the project owner can share the project")
    if await uow.shares.count_pending(project_id, now, except_email=email) >= MAX_PENDING_SHARES:
        raise TooManyRequestsError("Too many pending share links for this project")
    token = new_token()
    token_hash = hash_token(token)
    expires_at = now + SHARE_TTL
    await uow.shares.put(project_id, email, token_hash, expires_at)
    await uow.shares.delete_expired(project_id, now)
    link = await uow.shares.find_pending(token_hash, now)
    assert link is not None
    text = _invitation(
        user.login, access.project.name, f"{public_url}/join?token={token}", expires_at
    )
    try:
        await mailer.send(OutgoingMail(to=email, subject=SUBJECT, text=text))
    except MailDeliveryError as err:
        reason = type(err.__cause__).__name__
        logger.warning(
            "share mail could not be sent project_id=%s reason=%s",
            project_id,
            reason,
            extra={"event": "share mail failed", "project_id": project_id, "reason": reason},
        )
        raise ServiceUnavailableError("Email could not be sent") from err
    await uow.commit()
    _log_event("project shared", user, project_id, email)
    return link


async def _access(uow: UnitOfWork, project_id: UUID, user: User) -> ProjectAccess:
    access = await uow.projects.get_for_user(project_id, user.id)
    if access is None:
        raise NotFoundError(_INVALID_LINK)
    return access


async def join(uow: UnitOfWork, user: User, token: str, *, now: datetime) -> JoinResult:
    link = await uow.shares.find_pending(hash_token(token), now)
    if link is None:
        raise NotFoundError(_INVALID_LINK)
    access = await uow.projects.get_for_user(link.project_id, user.id)
    if access is not None:
        return JoinResult(access, already_member=True)
    try:
        await uow.projects.add_member(link.project_id, user.id)
    except ConflictError:
        return JoinResult(await _access(uow, link.project_id, user), already_member=True)
    except NotFoundError as err:
        raise NotFoundError(_INVALID_LINK) from err
    if not await uow.shares.claim(link.id):
        raise NotFoundError(_INVALID_LINK)
    access = await _access(uow, link.project_id, user)
    await uow.commit()
    _log_event("project joined", user, link.project_id, link.email)
    return JoinResult(access, already_member=False)
