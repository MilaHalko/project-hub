from datetime import datetime
from uuid import uuid4

from fastapi.testclient import TestClient

from tests.support.auth import bearer, signed_in
from tests.support.projects import add_participant, create_project


def test_owner_sees_members(api_client: TestClient, migrated_database_url: str) -> None:
    mila_id, mila = signed_in(api_client)
    zoe_id, _ = signed_in(api_client, "zoe")
    anna_id, _ = signed_in(api_client, "anna")
    created = create_project(api_client, mila)
    add_participant(migrated_database_url, created["id"], zoe_id)
    add_participant(migrated_database_url, created["id"], anna_id)

    r = api_client.get(f"/project/{created['id']}/members", headers=bearer(mila))

    assert r.status_code == 200
    members = r.json()
    assert [{k: m[k] for k in ("id", "login", "role")} for m in members] == [
        {"id": mila_id, "login": "mila", "role": "owner"},
        {"id": zoe_id, "login": "zoe", "role": "participant"},
        {"id": anna_id, "login": "anna", "role": "participant"},
    ]
    assert all(set(m) == {"id", "login", "role", "joined_at"} for m in members)
    assert members[0]["joined_at"] == created["created_at"]
    joined = [datetime.fromisoformat(m["joined_at"]) for m in members]
    assert joined[0] < joined[1] < joined[2]


def test_participant_sees_same_members(api_client: TestClient, migrated_database_url: str) -> None:
    _, mila = signed_in(api_client)
    anna_id, anna = signed_in(api_client, "anna")
    created = create_project(api_client, mila)
    add_participant(migrated_database_url, created["id"], anna_id)

    as_owner = api_client.get(f"/project/{created['id']}/members", headers=bearer(mila))
    as_participant = api_client.get(f"/project/{created['id']}/members", headers=bearer(anna))

    assert as_participant.status_code == 200
    assert as_participant.json() == as_owner.json()
    assert [m["login"] for m in as_participant.json()] == ["mila", "anna"]


def test_outsider_and_unknown_id_get_404(api_client: TestClient) -> None:
    _, mila = signed_in(api_client)
    _, anna = signed_in(api_client, "anna")
    created = create_project(api_client, mila)

    outsider = api_client.get(f"/project/{created['id']}/members", headers=bearer(anna))
    unknown = api_client.get(f"/project/{uuid4()}/members", headers=bearer(anna))

    assert outsider.status_code == unknown.status_code == 404
    assert outsider.json() == unknown.json() == {"detail": "Project not found"}
