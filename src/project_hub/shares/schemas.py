from datetime import datetime
from typing import Annotated, Self

from pydantic import AfterValidator, BaseModel, BeforeValidator, EmailStr, StringConstraints

from project_hub.projects.schemas import ProjectResponse
from project_hub.shares.entities import JoinResult, ShareLink


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

    @classmethod
    def from_link(cls, link: ShareLink) -> Self:
        return cls(email=link.email, expires_at=link.expires_at)


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
