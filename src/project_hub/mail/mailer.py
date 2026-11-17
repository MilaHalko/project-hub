import asyncio
import smtplib
from dataclasses import dataclass
from email.message import EmailMessage
from typing import TYPE_CHECKING, Protocol

import boto3
from botocore.config import Config
from botocore.exceptions import BotoCoreError, ClientError

from project_hub.core.config import Settings

if TYPE_CHECKING:
    from mypy_boto3_ses.client import SESClient


@dataclass(frozen=True)
class OutgoingMail:
    to: str
    subject: str
    text: str


class MailDeliveryError(Exception):
    pass


class Mailer(Protocol):
    async def send(self, mail: OutgoingMail) -> None: ...


class SmtpMailer:
    def __init__(self, host: str, port: int, sender: str, *, timeout: float = 10) -> None:
        self._host = host
        self._port = port
        self._sender = sender
        self._timeout = timeout

    async def send(self, mail: OutgoingMail) -> None:
        message = EmailMessage()
        message["From"] = self._sender
        message["To"] = mail.to
        message["Subject"] = mail.subject
        message.set_content(mail.text, charset="utf-8")
        try:
            await asyncio.to_thread(self._deliver, message)
        except (smtplib.SMTPException, OSError) as err:
            raise MailDeliveryError from err

    def _deliver(self, message: EmailMessage) -> None:
        with smtplib.SMTP(self._host, self._port, timeout=self._timeout) as smtp:
            smtp.send_message(message)


class SesMailer:
    def __init__(self, client: "SESClient", sender: str) -> None:
        self._client = client
        self._sender = sender

    async def send(self, mail: OutgoingMail) -> None:
        try:
            await asyncio.to_thread(self._deliver, mail)
        except (BotoCoreError, ClientError) as err:
            raise MailDeliveryError from err

    def _deliver(self, mail: OutgoingMail) -> None:
        self._client.send_email(
            Source=self._sender,
            Destination={"ToAddresses": [mail.to]},
            Message={
                "Subject": {"Data": mail.subject, "Charset": "UTF-8"},
                "Body": {"Text": {"Data": mail.text, "Charset": "UTF-8"}},
            },
        )


def create_ses_client(settings: Settings) -> "SESClient":
    config = Config(
        connect_timeout=5, read_timeout=10, retries={"max_attempts": 2, "mode": "standard"}
    )
    return boto3.client("ses", region_name=settings.ses_region, config=config)  # pyright: ignore[reportUnknownMemberType]


def create_mailer(settings: Settings) -> Mailer | None:
    if settings.mail_backend == "ses":
        return SesMailer(create_ses_client(settings), settings.mail_from)
    if settings.smtp_host is None:
        return None
    return SmtpMailer(settings.smtp_host, settings.smtp_port, settings.mail_from)
