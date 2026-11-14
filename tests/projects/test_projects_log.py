import logging
from uuid import UUID

import pytest
from fastapi.testclient import TestClient

from tests.support.auth import signed_in
from tests.support.projects import create_project

LOGGER = "project_hub.projects.service"


def _field(record: logging.LogRecord, name: str) -> object:
    return getattr(record, name)


def test_create_is_logged_without_name(
    api_client: TestClient, caplog: pytest.LogCaptureFixture
) -> None:
    user_id, token = signed_in(api_client)

    with caplog.at_level(logging.INFO, logger=LOGGER):
        created = create_project(api_client, token, name="Secret diploma")

    (record,) = [r for r in caplog.records if r.name == LOGGER]
    assert record.levelno == logging.INFO
    assert _field(record, "event") == "project created"
    assert _field(record, "login") == "mila"
    assert _field(record, "user_id") == UUID(user_id)
    assert _field(record, "project_id") == UUID(created["id"])
    assert "Secret diploma" not in record.getMessage()
