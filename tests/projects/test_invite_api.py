from typing import Any
from uuid import uuid4

import httpx2
import pytest
from fastapi.testclient import TestClient

from tests.support.auth import bearer, signed_in
from tests.support.projects import add_participant, create_project


def invite(client: TestClient, token: str, project_id: str, login: str) -> httpx2.Response:
    return client.post(
        f"/project/{project_id}/invite", params={"user": login}, headers=bearer(token)
    )


def members(client: TestClient, token: str, project_id: str) -> list[dict[str, Any]]:
    r = client.get(f"/project/{project_id}/members", headers=bearer(token))
    assert r.status_code == 200, r.text
    body: list[dict[str, Any]] = r.json()
    return body


def test_owner_invites_user(api_client: TestClient, migrated_database_url: str) -> None:
    _, mila = signed_in(api_client)
    anna_id, anna = signed_in(api_client, "anna")
    created = create_project(api_client, mila)

    r = invite(api_client, mila, created["id"], "anna")

    assert r.status_code == 201
    body = r.json()
    assert body == {
        "id": anna_id,
        "login": "anna",
        "role": "participant",
        "joined_at": body["joined_at"],
    }
    info = api_client.get(f"/project/{created['id']}/info", headers=bearer(anna))
    assert info.status_code == 200
    assert info.json()["my_role"] == "participant"
    listed = api_client.get("/projects", params={"role": "participant"}, headers=bearer(anna))
    assert [p["id"] for p in listed.json()] == [created["id"]]
    assert members(api_client, mila, created["id"])[1] == body


def test_participant_cannot_invite(api_client: TestClient, migrated_database_url: str) -> None:
    _, mila = signed_in(api_client)
    anna_id, anna = signed_in(api_client, "anna")
    _, zoe = signed_in(api_client, "zoe")
    created = create_project(api_client, mila)
    add_participant(migrated_database_url, created["id"], anna_id)

    r = invite(api_client, anna, created["id"], "zoe")

    assert r.status_code == 403
    assert r.json() == {"detail": "Only the project owner can invite users"}
    assert api_client.get(f"/project/{created['id']}/info", headers=bearer(zoe)).status_code == 404


def test_outsider_and_unknown_project_get_404(api_client: TestClient) -> None:
    _, mila = signed_in(api_client)
    _, outsider = signed_in(api_client, "outsider")
    signed_in(api_client, "anna")
    created = create_project(api_client, mila)

    responses = [
        invite(api_client, outsider, created["id"], "anna"),
        invite(api_client, outsider, created["id"], "nobody"),
        invite(api_client, mila, str(uuid4()), "anna"),
    ]

    assert [r.status_code for r in responses] == [404, 404, 404]
    assert all(r.json() == {"detail": "Project not found"} for r in responses)
    assert [m["login"] for m in members(api_client, mila, created["id"])] == ["mila"]


def test_invite_unknown_login_is_user_not_found(api_client: TestClient) -> None:
    _, mila = signed_in(api_client)
    created = create_project(api_client, mila)

    r = invite(api_client, mila, created["id"], "nobody")

    assert r.status_code == 404
    assert r.json() == {"detail": "User not found"}


def test_invite_login_is_exact(api_client: TestClient) -> None:
    _, mila = signed_in(api_client)
    signed_in(api_client, "anna")
    created = create_project(api_client, mila)

    for login in ("Anna", " anna"):
        r = invite(api_client, mila, created["id"], login)
        assert r.status_code == 404
        assert r.json() == {"detail": "User not found"}


def test_invite_odd_but_valid_login_is_user_not_found(api_client: TestClient) -> None:
    _, mila = signed_in(api_client)
    signed_in(api_client, "anna")
    created = create_project(api_client, mila)

    for login in ("аня", "anna\n"):
        r = invite(api_client, mila, created["id"], login)
        assert r.status_code == 404
        assert r.json() == {"detail": "User not found"}


def test_owner_cannot_invite_self(api_client: TestClient) -> None:
    mila_id, mila = signed_in(api_client)
    created = create_project(api_client, mila)

    r = invite(api_client, mila, created["id"], "mila")

    assert r.status_code == 409
    assert r.json() == {"detail": "You already own this project"}
    assert [(m["id"], m["role"]) for m in members(api_client, mila, created["id"])] == [
        (mila_id, "owner")
    ]


def test_invite_existing_participant_conflicts(api_client: TestClient) -> None:
    _, mila = signed_in(api_client)
    signed_in(api_client, "anna")
    created = create_project(api_client, mila)

    first = invite(api_client, mila, created["id"], "anna")
    second = invite(api_client, mila, created["id"], "anna")

    assert first.status_code == 201
    assert second.status_code == 409
    assert second.json() == {"detail": "User is already a participant of this project"}
    assert members(api_client, mila, created["id"])[1]["joined_at"] == first.json()["joined_at"]


@pytest.mark.parametrize("params", [{}, {"user": ""}, {"user": "a" * 33}, {"user": "an\x00na"}])
def test_invite_bad_user_param_is_422(api_client: TestClient, params: dict[str, str]) -> None:
    _, mila = signed_in(api_client)
    signed_in(api_client, "anna")
    created = create_project(api_client, mila)

    r = api_client.post(f"/project/{created['id']}/invite", params=params, headers=bearer(mila))

    assert r.status_code == 422
    assert isinstance(r.json()["detail"], list)
    assert [m["login"] for m in members(api_client, mila, created["id"])] == ["mila"]


def test_invite_bad_project_id_is_422(api_client: TestClient) -> None:
    _, mila = signed_in(api_client)

    r = api_client.post("/project/not-a-uuid/invite", params={"user": "anna"}, headers=bearer(mila))

    assert r.status_code == 422


def test_invite_keeps_updated_at(api_client: TestClient) -> None:
    _, mila = signed_in(api_client)
    signed_in(api_client, "anna")
    created = create_project(api_client, mila)
    path = f"/project/{created['id']}/info"

    before = api_client.get(path, headers=bearer(mila)).json()["updated_at"]
    assert invite(api_client, mila, created["id"], "anna").status_code == 201
    after = api_client.get(path, headers=bearer(mila)).json()["updated_at"]

    assert before == after
