from datetime import datetime
from typing import Annotated, Self

from pydantic import AfterValidator, BaseModel, BeforeValidator, EmailStr, StringConstraints

from project_hub.mail.mailer import MailResult
from project_hub.projects.schemas import ProjectResponse
from project_hub.shares.entities import JoinResult, ShareResult


def _reject_surrounding_whitespace(value: object) -> object:
    if isinstance(value, str) and value != value.strip():
        raise ValueError("Email must not start or end with whitespace")
    return value


ShareEmail = Annotated[
    EmailStr,
    StringConstraints(max_length=254),
    BeforeValidator(_reject_surrounding_whitespace),
    AfterValidator(str.lower),
]


class ShareResponse(BaseModel):
    email: str
    expires_at: datetime
    message: str | None = None

    @classmethod
    def from_result(cls, result: ShareResult) -> Self:
        link = result.link
        message = None
        if result.mail is MailResult.RECIPIENT_NOT_VERIFIED:
            message = (
                f"No mail was sent yet. {link.email} must first click the verification email "
                "from AWS. Then share again."
            )
        return cls(email=link.email, expires_at=link.expires_at, message=message)


class JoinResponse(BaseModel):
    login: str
    already_member: bool
    project: ProjectResponse

    @classmethod
    def from_result(cls, login: str, result: JoinResult) -> Self:
        return cls(
            login=login,
            already_member=result.already_member,
            project=ProjectResponse.from_access(result.access),
        )
