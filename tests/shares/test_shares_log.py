import logging
from collections.abc import Callable
from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient

from tests.support.auth import signed_in
from tests.support.mail import random_address
from tests.support.projects import add_participant, create_project
from tests.support.shares import closed_port, share

LOGGER = "project_hub.shares.service"


def _field(record: logging.LogRecord, name: str) -> object:
    return getattr(record, name)


def _security_events(caplog: pytest.LogCaptureFixture) -> list[logging.LogRecord]:
    return [r for r in caplog.records if r.name == LOGGER and r.levelno == logging.INFO]


def test_share_is_logged_only_when_it_happens(
    api_client: TestClient,
    make_api_client: Callable[..., TestClient],
    mailpit_url: str,
    migrated_database_url: str,
    caplog: pytest.LogCaptureFixture,
) -> None:
    mila_id, mila = signed_in(api_client)
    anna_id, anna = signed_in(api_client, "anna")
    _, zoe = signed_in(api_client, "zoe")
    created = create_project(api_client, mila)
    full = create_project(api_client, mila, name="Full")
    add_participant(migrated_database_url, created["id"], anna_id)
    for _ in range(10):
        assert share(api_client, mila, full["id"], random_address()).status_code == 200
    unconfigured = make_api_client(smtp_host=None)
    broken = make_api_client(smtp_host="127.0.0.1", smtp_port=closed_port())
    address = random_address()

    caplog.clear()
    with caplog.at_level(logging.INFO, logger=LOGGER):
        assert share(api_client, anna, created["id"], address).status_code == 403
        assert share(api_client, zoe, created["id"], address).status_code == 404
        assert share(api_client, mila, str(uuid4()), address).status_code == 404
        assert share(api_client, mila, created["id"], "not-an-email").status_code == 422
        assert share(unconfigured, mila, created["id"], address).status_code == 503
        assert share(broken, mila, created["id"], address).status_code == 503
        assert share(api_client, mila, full["id"], address).status_code == 429
        assert not _security_events(caplog)

        assert share(api_client, mila, created["id"], address).status_code == 200

    (record,) = _security_events(caplog)
    assert _field(record, "event") == "project shared"
    assert _field(record, "login") == "mila"
    assert _field(record, "user_id") == UUID(mila_id)
    assert _field(record, "project_id") == UUID(created["id"])
    assert _field(record, "email") == address
    assert "project shared" in record.getMessage()


def test_mail_failure_is_a_warning_without_the_link(
    api_client: TestClient,
    make_api_client: Callable[..., TestClient],
    caplog: pytest.LogCaptureFixture,
) -> None:
    _, mila = signed_in(api_client)
    created = create_project(api_client, mila)
    broken = make_api_client(smtp_host="127.0.0.1", smtp_port=closed_port())

    caplog.clear()
    with caplog.at_level(logging.INFO, logger=LOGGER):
        assert share(broken, mila, created["id"], random_address()).status_code == 503

    (record,) = [r for r in caplog.records if r.name == LOGGER]
    assert record.levelno == logging.WARNING
    assert _field(record, "project_id") == UUID(created["id"])
    assert _field(record, "reason") == "ConnectionRefusedError"
    assert "reason=ConnectionRefusedError" in record.getMessage()
    assert "token" not in record.getMessage()
    assert "join" not in record.getMessage()
