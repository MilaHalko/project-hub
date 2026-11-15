import logging
from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient

from tests.support.auth import bearer, signed_in
from tests.support.projects import add_participant, create_project

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


def test_delete_is_logged_only_when_it_happens(
    api_client: TestClient, migrated_database_url: str, caplog: pytest.LogCaptureFixture
) -> None:
    mila_id, mila = signed_in(api_client)
    anna_id, anna = signed_in(api_client, "anna")
    _, stranger = signed_in(api_client, "stranger")
    created = create_project(api_client, mila)
    add_participant(migrated_database_url, created["id"], anna_id)
    path = f"/project/{created['id']}"

    caplog.clear()
    with caplog.at_level(logging.INFO, logger=LOGGER):
        assert api_client.delete(path, headers=bearer(anna)).status_code == 403
        assert api_client.delete(path, headers=bearer(stranger)).status_code == 404
        assert api_client.delete(f"/project/{uuid4()}", headers=bearer(mila)).status_code == 404
        assert not [r for r in caplog.records if r.name == LOGGER]

        assert api_client.delete(path, headers=bearer(mila)).status_code == 204

    (record,) = [r for r in caplog.records if r.name == LOGGER]
    assert record.levelno == logging.INFO
    assert _field(record, "event") == "project deleted"
    assert _field(record, "login") == "mila"
    assert _field(record, "user_id") == UUID(mila_id)
    assert _field(record, "project_id") == UUID(created["id"])


def test_invite_is_logged_only_when_it_happens(
    api_client: TestClient, migrated_database_url: str, caplog: pytest.LogCaptureFixture
) -> None:
    mila_id, mila = signed_in(api_client)
    anna_id, anna = signed_in(api_client, "anna")
    zoe_id, _ = signed_in(api_client, "zoe")
    _, stranger = signed_in(api_client, "stranger")
    created = create_project(api_client, mila)
    add_participant(migrated_database_url, created["id"], anna_id)
    path = f"/project/{created['id']}/invite"

    caplog.clear()
    with caplog.at_level(logging.INFO, logger=LOGGER):
        assert (
            api_client.post(path, params={"user": "zoe"}, headers=bearer(anna)).status_code == 403
        )
        assert (
            api_client.post(path, params={"user": "zoe"}, headers=bearer(stranger)).status_code
            == 404
        )
        assert (
            api_client.post(path, params={"user": "nobody"}, headers=bearer(mila)).status_code
            == 404
        )
        assert (
            api_client.post(path, params={"user": "mila"}, headers=bearer(mila)).status_code == 409
        )
        assert (
            api_client.post(path, params={"user": "anna"}, headers=bearer(mila)).status_code == 409
        )
        assert (
            api_client.post(
                f"/project/{uuid4()}/invite", params={"user": "anna"}, headers=bearer(mila)
            ).status_code
            == 404
        )
        assert api_client.post(path, params={"user": ""}, headers=bearer(mila)).status_code == 422
        assert not [r for r in caplog.records if r.name == LOGGER]

        assert (
            api_client.post(path, params={"user": "zoe"}, headers=bearer(mila)).status_code == 201
        )

    (record,) = [r for r in caplog.records if r.name == LOGGER]
    assert record.levelno == logging.INFO
    assert _field(record, "event") == "participant invited"
    assert _field(record, "login") == "mila"
    assert _field(record, "user_id") == UUID(mila_id)
    assert _field(record, "project_id") == UUID(created["id"])
    assert _field(record, "member_id") == UUID(zoe_id)
