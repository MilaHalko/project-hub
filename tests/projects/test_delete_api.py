from typing import Any
from uuid import uuid4

from fastapi.testclient import TestClient

from tests.support.auth import bearer, signed_in
from tests.support.projects import add_participant, create_project


def _delete(client: TestClient, token: str, project_id: str) -> Any:
    return client.delete(f"/project/{project_id}", headers=bearer(token))


def _info_status(client: TestClient, token: str, project_id: str) -> int:
    return client.get(f"/project/{project_id}/info", headers=bearer(token)).status_code


def _listed_ids(client: TestClient, token: str) -> list[str]:
    return [p["id"] for p in client.get("/projects", headers=bearer(token)).json()]


def test_owner_deletes_project(api_client: TestClient, migrated_database_url: str) -> None:
    _, mila = signed_in(api_client)
    anna_id, anna = signed_in(api_client, "anna")
    created = create_project(api_client, mila)
    add_participant(migrated_database_url, created["id"], anna_id)

    r = _delete(api_client, mila, created["id"])

    assert r.status_code == 204
    assert r.content == b""
    assert _info_status(api_client, mila, created["id"]) == 404
    assert _info_status(api_client, anna, created["id"]) == 404
    assert created["id"] not in _listed_ids(api_client, mila)
    assert created["id"] not in _listed_ids(api_client, anna)


def test_participant_cannot_delete(api_client: TestClient, migrated_database_url: str) -> None:
    _, mila = signed_in(api_client)
    anna_id, anna = signed_in(api_client, "anna")
    created = create_project(api_client, mila)
    add_participant(migrated_database_url, created["id"], anna_id)

    r = _delete(api_client, anna, created["id"])

    assert r.status_code == 403
    assert r.json() == {"detail": "Only the project owner can delete the project"}
    assert _info_status(api_client, mila, created["id"]) == 200
    assert _info_status(api_client, anna, created["id"]) == 200


def test_outsider_and_unknown_id_get_404(api_client: TestClient) -> None:
    _, mila = signed_in(api_client)
    _, anna = signed_in(api_client, "anna")
    created = create_project(api_client, mila)

    outsider = _delete(api_client, anna, created["id"])
    unknown = _delete(api_client, anna, str(uuid4()))

    assert outsider.status_code == unknown.status_code == 404
    assert outsider.json() == unknown.json() == {"detail": "Project not found"}
    assert _info_status(api_client, mila, created["id"]) == 200
