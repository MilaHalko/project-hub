from datetime import datetime
from typing import Any
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from tests.projects.invalid_bodies import INVALID_BODIES
from tests.support.auth import bearer, signed_in
from tests.support.projects import add_participant, create_project


def _put(client: TestClient, token: str, project_id: str, body: dict[str, Any]) -> Any:
    return client.put(f"/project/{project_id}/info", headers=bearer(token), json=body)


def _get(client: TestClient, token: str, project_id: str) -> Any:
    return client.get(f"/project/{project_id}/info", headers=bearer(token))


def test_owner_updates_info(api_client: TestClient) -> None:
    _, token = signed_in(api_client)
    created = create_project(api_client, token, "Diploma", "Old")

    r = _put(api_client, token, created["id"], {"name": "  Thesis  ", "description": "New"})

    assert r.status_code == 200
    body = r.json()
    assert body["name"] == "Thesis"
    assert body["description"] == "New"
    assert body["my_role"] == "owner"
    assert body["created_at"] == created["created_at"]
    assert datetime.fromisoformat(body["updated_at"]) > datetime.fromisoformat(
        created["updated_at"]
    )
    assert _get(api_client, token, created["id"]).json() == body


def test_participant_updates_info(api_client: TestClient, migrated_database_url: str) -> None:
    _, mila = signed_in(api_client)
    anna_id, anna = signed_in(api_client, "anna")
    created = create_project(api_client, mila)
    add_participant(migrated_database_url, created["id"], anna_id)

    r = _put(api_client, anna, created["id"], {"name": "Thesis", "description": "New"})

    assert r.status_code == 200
    assert r.json()["name"] == "Thesis"
    assert _get(api_client, mila, created["id"]).json()["description"] == "New"


def test_participant_update_keeps_owner_and_role(
    api_client: TestClient, migrated_database_url: str
) -> None:
    mila_id, mila = signed_in(api_client)
    anna_id, anna = signed_in(api_client, "anna")
    created = create_project(api_client, mila)
    add_participant(migrated_database_url, created["id"], anna_id)

    r = _put(api_client, anna, created["id"], {"name": "Thesis"})

    assert r.status_code == 200
    assert r.json()["owner"] == {"id": mila_id, "login": "mila"}
    assert r.json()["my_role"] == "participant"
    assert _get(api_client, mila, created["id"]).json()["my_role"] == "owner"


def test_outsider_and_unknown_id_get_404_and_nothing_changes(api_client: TestClient) -> None:
    _, mila = signed_in(api_client)
    _, anna = signed_in(api_client, "anna")
    created = create_project(api_client, mila, "Diploma", "Old")
    body = {"name": "Thesis", "description": "New"}

    outsider = _put(api_client, anna, created["id"], body)
    unknown = _put(api_client, anna, str(uuid4()), body)

    assert outsider.status_code == unknown.status_code == 404
    assert outsider.json() == unknown.json() == {"detail": "Project not found"}
    assert _get(api_client, mila, created["id"]).json() == created


@pytest.mark.parametrize("payload", INVALID_BODIES)
def test_invalid_body_is_422_and_nothing_changes(
    api_client: TestClient, payload: dict[str, Any]
) -> None:
    _, token = signed_in(api_client)
    created = create_project(api_client, token, "Diploma", "Old")

    r = _put(api_client, token, created["id"], payload)

    assert r.status_code == 422
    assert _get(api_client, token, created["id"]).json() == created


def test_omitted_description_becomes_empty(api_client: TestClient) -> None:
    _, token = signed_in(api_client)
    created = create_project(api_client, token, "Diploma", "Old")

    r = _put(api_client, token, created["id"], {"name": "Thesis"})

    assert r.status_code == 200
    assert r.json()["description"] == ""
    assert _get(api_client, token, created["id"]).json()["description"] == ""
