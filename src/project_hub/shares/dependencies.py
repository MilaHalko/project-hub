from typing import Annotated

from fastapi import Depends, Request

from project_hub.core.config import Settings
from project_hub.core.exceptions import ServiceUnavailableError
from project_hub.mail.mailer import Mailer

_NOT_CONFIGURED = "Email sharing is not configured"


def get_share_mailer(request: Request) -> Mailer:
    mailer: Mailer | None = request.app.state.mailer
    settings: Settings = request.app.state.settings
    if mailer is None or settings.public_url is None:
        raise ServiceUnavailableError(_NOT_CONFIGURED)
    return mailer


def get_public_url(request: Request) -> str:
    settings: Settings = request.app.state.settings
    if settings.public_url is None:
        raise ServiceUnavailableError(_NOT_CONFIGURED)
    return settings.public_url


ShareMailer = Annotated[Mailer, Depends(get_share_mailer)]
PublicUrl = Annotated[str, Depends(get_public_url)]
