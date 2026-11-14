from uuid import uuid4

from fastapi.testclient import TestClient

from tests.support.auth import bearer, signed_in
from tests.support.projects import add_participant, create_project


def test_owner_reads_info(api_client: TestClient) -> None:
    _, token = signed_in(api_client)
    created = create_project(api_client, token, description="Final project")

    r = api_client.get(f"/project/{created['id']}/info", headers=bearer(token))

    assert r.status_code == 200
    assert r.json() == created


def test_outsider_gets_same_404_as_unknown_id(api_client: TestClient) -> None:
    _, mila = signed_in(api_client)
    _, anna = signed_in(api_client, "anna")
    created = create_project(api_client, mila)

    outsider = api_client.get(f"/project/{created['id']}/info", headers=bearer(anna))
    unknown = api_client.get(f"/project/{uuid4()}/info", headers=bearer(anna))

    assert outsider.status_code == 404
    assert unknown.status_code == 404
    assert outsider.json() == unknown.json() == {"detail": "Project not found"}


def test_non_uuid_id_is_422(api_client: TestClient) -> None:
    _, token = signed_in(api_client)

    r = api_client.get("/project/not-a-uuid/info", headers=bearer(token))

    assert r.status_code == 422


def test_participant_reads_info(api_client: TestClient, migrated_database_url: str) -> None:
    mila_id, mila = signed_in(api_client)
    anna_id, anna = signed_in(api_client, "anna")
    created = create_project(api_client, mila)
    add_participant(migrated_database_url, created["id"], anna_id)

    r = api_client.get(f"/project/{created['id']}/info", headers=bearer(anna))

    assert r.status_code == 200
    assert r.json()["my_role"] == "participant"
    assert r.json()["owner"] == {"id": mila_id, "login": "mila"}
