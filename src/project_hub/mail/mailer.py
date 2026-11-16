import asyncio
import smtplib
from dataclasses import dataclass
from email.message import EmailMessage
from typing import Protocol

from project_hub.core.config import Settings


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


def create_mailer(settings: Settings) -> Mailer | None:
    if settings.smtp_host is None:
        return None
    return SmtpMailer(settings.smtp_host, settings.smtp_port, settings.mail_from)
