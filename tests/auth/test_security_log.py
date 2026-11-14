import logging
from uuid import UUID

import pytest
from fastapi.testclient import TestClient

from tests.support.auth import bearer, login, register

LOGGER = "project_hub.auth.service"
OLD_PASSWORD = "correct-horse-1"
NEW_PASSWORD = "battery-staple-2"


def _auth_records(caplog: pytest.LogCaptureFixture) -> list[logging.LogRecord]:
    return [r for r in caplog.records if r.name == LOGGER]


def _field(record: logging.LogRecord, name: str) -> object:
    return getattr(record, name)


def test_security_events_are_logged_without_secrets(
    api_client: TestClient, caplog: pytest.LogCaptureFixture
) -> None:
    with caplog.at_level(logging.INFO, logger=LOGGER):
        registered = register(api_client, password=OLD_PASSWORD)
        wrong = api_client.post("/login", json={"login": "mila", "password": "wrong-pass-99"})
        assert wrong.status_code == 401
        first_token = login(api_client, password=OLD_PASSWORD)
        changed = api_client.put(
            "/users/me/password",
            headers=bearer(first_token),
            json={
                "current_password": OLD_PASSWORD,
                "new_password": NEW_PASSWORD,
                "repeat_new_password": NEW_PASSWORD,
            },
        )
        assert changed.status_code == 200
        second_token = str(changed.json()["access_token"])
        assert api_client.post("/logout", headers=bearer(second_token)).status_code == 204

    records = _auth_records(caplog)
    events = [_field(r, "event") for r in records]
    assert events == [
        "user registered",
        "login failed",
        "login succeeded",
        "password changed",
        "logout",
    ]
    secrets = [OLD_PASSWORD, NEW_PASSWORD, "wrong-pass-99", "$argon2"]
    secrets += [first_token, second_token]
    for record in records:
        assert record.levelno == logging.INFO
        for text in (record.getMessage(), str(record.__dict__)):
            for secret in secrets:
                assert secret not in text
    assert _field(records[0], "login") == "mila"
    assert _field(records[0], "user_id") == UUID(str(registered.json()["id"]))


def test_failed_login_message_cannot_be_forged_with_newlines(
    api_client: TestClient, caplog: pytest.LogCaptureFixture
) -> None:
    with caplog.at_level(logging.INFO, logger=LOGGER):
        r = api_client.post(
            "/login", json={"login": "mila\nlogin succeeded", "password": "wrong-pass-99"}
        )
    assert r.status_code == 401
    (record,) = _auth_records(caplog)
    assert "\n" not in record.getMessage()
    assert _field(record, "event") == "login failed"
    assert not hasattr(record, "user_id")
