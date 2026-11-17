from collections.abc import Iterator
from typing import Any

import boto3
import pytest
from moto import mock_aws
from moto.core.models import DEFAULT_ACCOUNT_ID
from moto.ses.models import ses_backends

from project_hub.mail.mailer import (
    MailDeliveryError,
    MailResult,
    OutgoingMail,
    SesMailer,
    create_mailer,
)
from tests.isolated_settings import IsolatedSettings

pytestmark = pytest.mark.anyio

REGION = "eu-west-1"
SENDER = "noreply@project-hub.test"
RECIPIENT = "friend@example.com"
SUBJECT = "You are invited to a project on Project Hub"


@pytest.fixture(autouse=True)
def aws_env(monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    monkeypatch.setenv("AWS_ACCESS_KEY_ID", "testing")
    monkeypatch.setenv("AWS_SECRET_ACCESS_KEY", "testing")
    with mock_aws():
        yield


def _verify(address: str) -> None:
    boto3.client("ses", region_name=REGION).verify_email_identity(EmailAddress=address)  # pyright: ignore[reportUnknownMemberType]


def _verify_recipient(address: str) -> None:
    boto3.client("sesv2", region_name=REGION).create_email_identity(EmailIdentity=address)  # pyright: ignore[reportUnknownMemberType]
    ses_backends[DEFAULT_ACCOUNT_ID][REGION].email_identities[
        address
    ].verified_for_sending_status = True


def _identity_status(address: str) -> bool | None:
    client = boto3.client("sesv2", region_name=REGION)  # pyright: ignore[reportUnknownMemberType]
    try:
        return client.get_email_identity(EmailIdentity=address)["VerifiedForSendingStatus"]
    except client.exceptions.NotFoundException:
        return None


def _sent() -> list[Any]:
    return ses_backends[DEFAULT_ACCOUNT_ID][REGION].sent_messages


async def test_send_delivers_a_plain_text_mail_through_ses() -> None:
    _verify(SENDER)
    _verify_recipient(RECIPIENT)
    mailer = create_mailer(IsolatedSettings(mail_backend="ses", mail_from=SENDER))
    assert isinstance(mailer, SesMailer)

    result = await mailer.send(
        OutgoingMail(to=RECIPIENT, subject=SUBJECT, text="Привіт\nhttp://x/join?token=abc")
    )

    assert result is MailResult.SENT

    (message,) = _sent()
    assert message.source == SENDER
    assert message.destinations["ToAddresses"] == [RECIPIENT]
    assert message.subject == SUBJECT
    assert "Привіт" in message.body
    assert "http://x/join?token=abc" in message.body


async def test_unknown_recipient_gets_a_verification_email_and_no_mail() -> None:
    _verify(SENDER)
    mailer = create_mailer(IsolatedSettings(mail_backend="ses", mail_from=SENDER))
    assert mailer is not None

    result = await mailer.send(OutgoingMail(to=RECIPIENT, subject=SUBJECT, text="x"))

    assert result is MailResult.RECIPIENT_NOT_VERIFIED
    assert _identity_status(RECIPIENT) is False
    assert _sent() == []


async def test_recipient_still_waiting_for_verification_gets_no_mail() -> None:
    _verify(SENDER)
    boto3.client("sesv2", region_name=REGION).create_email_identity(EmailIdentity=RECIPIENT)  # pyright: ignore[reportUnknownMemberType]
    mailer = create_mailer(IsolatedSettings(mail_backend="ses", mail_from=SENDER))
    assert mailer is not None

    result = await mailer.send(OutgoingMail(to=RECIPIENT, subject=SUBJECT, text="x"))

    assert result is MailResult.RECIPIENT_NOT_VERIFIED
    assert _sent() == []


async def test_send_from_an_unverified_sender_raises_mail_delivery_error() -> None:
    _verify_recipient(RECIPIENT)
    mailer = create_mailer(IsolatedSettings(mail_backend="ses", mail_from=SENDER))
    assert mailer is not None

    with pytest.raises(MailDeliveryError):
        await mailer.send(OutgoingMail(to=RECIPIENT, subject=SUBJECT, text="x"))

    assert _sent() == []


def test_smtp_backend_stays_the_default() -> None:
    assert create_mailer(IsolatedSettings()) is None
    assert create_mailer(IsolatedSettings(smtp_host="localhost")) is not None
    assert not isinstance(create_mailer(IsolatedSettings(smtp_host="localhost")), SesMailer)
