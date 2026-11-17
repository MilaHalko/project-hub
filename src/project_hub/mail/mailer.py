import asyncio
import smtplib
from dataclasses import dataclass
from email.message import EmailMessage
from enum import StrEnum
from typing import TYPE_CHECKING, Protocol

import boto3
from botocore.config import Config
from botocore.exceptions import BotoCoreError, ClientError

from project_hub.core.config import Settings

if TYPE_CHECKING:
    from mypy_boto3_ses.client import SESClient
    from mypy_boto3_sesv2.client import SESV2Client


@dataclass(frozen=True)
class OutgoingMail:
    to: str
    subject: str
    text: str


class MailResult(StrEnum):
    SENT = "sent"
    RECIPIENT_NOT_VERIFIED = "recipient_not_verified"


class MailDeliveryError(Exception):
    pass


class Mailer(Protocol):
    async def send(self, mail: OutgoingMail) -> MailResult: ...


class SmtpMailer:
    def __init__(self, host: str, port: int, sender: str, *, timeout: float = 10) -> None:
        self._host = host
        self._port = port
        self._sender = sender
        self._timeout = timeout

    async def send(self, mail: OutgoingMail) -> MailResult:
        message = EmailMessage()
        message["From"] = self._sender
        message["To"] = mail.to
        message["Subject"] = mail.subject
        message.set_content(mail.text, charset="utf-8")
        try:
            await asyncio.to_thread(self._deliver, message)
        except (smtplib.SMTPException, OSError) as err:
            raise MailDeliveryError from err
        return MailResult.SENT

    def _deliver(self, message: EmailMessage) -> None:
        with smtplib.SMTP(self._host, self._port, timeout=self._timeout) as smtp:
            smtp.send_message(message)


class SesMailer:
    def __init__(self, mail: "SESClient", identities: "SESV2Client", sender: str) -> None:
        self._mail = mail
        self._identities = identities
        self._sender = sender

    async def send(self, mail: OutgoingMail) -> MailResult:
        try:
            return await asyncio.to_thread(self._deliver, mail)
        except (BotoCoreError, ClientError) as err:
            raise MailDeliveryError from err

    def _deliver(self, mail: OutgoingMail) -> MailResult:
        if not self._is_verified(mail.to):
            return MailResult.RECIPIENT_NOT_VERIFIED
        self._mail.send_email(
            Source=self._sender,
            Destination={"ToAddresses": [mail.to]},
            Message={
                "Subject": {"Data": mail.subject, "Charset": "UTF-8"},
                "Body": {"Text": {"Data": mail.text, "Charset": "UTF-8"}},
            },
        )
        return MailResult.SENT

    def _is_verified(self, address: str) -> bool:
        try:
            identity = self._identities.get_email_identity(EmailIdentity=address)
        except self._identities.exceptions.NotFoundException:
            self._identities.create_email_identity(EmailIdentity=address)
            return False
        return identity["VerifiedForSendingStatus"]


def _aws_config() -> Config:
    return Config(
        connect_timeout=5, read_timeout=10, retries={"max_attempts": 2, "mode": "standard"}
    )


def create_mailer(settings: Settings) -> Mailer | None:
    if settings.mail_backend == "ses":
        return SesMailer(
            boto3.client("ses", region_name=settings.ses_region, config=_aws_config()),  # pyright: ignore[reportUnknownMemberType]
            boto3.client("sesv2", region_name=settings.ses_region, config=_aws_config()),  # pyright: ignore[reportUnknownMemberType]
            settings.mail_from,
        )
    if settings.smtp_host is None:
        return None
    return SmtpMailer(settings.smtp_host, settings.smtp_port, settings.mail_from)
