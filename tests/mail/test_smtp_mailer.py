import socket

import pytest

from project_hub.mail.mailer import MailDeliveryError, OutgoingMail, SmtpMailer
from tests.support.mail import messages_to, random_address

pytestmark = pytest.mark.anyio

SENDER = "noreply@project-hub.test"
SUBJECT = "You are invited to a project on Project Hub"


async def test_send_delivers_a_plain_text_mail(smtp_port: int, mailpit_url: str) -> None:
    address = random_address()
    mailer = SmtpMailer("localhost", smtp_port, SENDER)

    await mailer.send(
        OutgoingMail(to=address, subject=SUBJECT, text="Привіт\nhttp://x/join?token=abc")
    )

    (message,) = messages_to(mailpit_url, address)
    assert message["From"]["Address"] == SENDER
    assert [to["Address"] for to in message["To"]] == [address]
    assert message["Subject"] == SUBJECT
    assert "Привіт" in message["Text"]
    assert "http://x/join?token=abc" in message["Text"]


async def test_send_to_an_unreachable_server_raises_mail_delivery_error() -> None:
    with socket.socket() as closed:
        closed.bind(("127.0.0.1", 0))
        port = closed.getsockname()[1]
    mailer = SmtpMailer("127.0.0.1", port, SENDER)

    with pytest.raises(MailDeliveryError):
        await mailer.send(OutgoingMail(to=random_address(), subject=SUBJECT, text="x"))
