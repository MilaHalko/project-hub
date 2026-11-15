from datetime import datetime
from typing import Any
from uuid import uuid4

import httpx2
import pytest
from fastapi.testclient import TestClient

from tests.support.auth import bearer, signed_in
from tests.support.projects import add_participant, create_project


def remove(client: TestClient, token: str, project_id: str, user_id: str) -> httpx2.Response:
    return client.delete(f"/project/{project_id}/members/{user_id}", headers=bearer(token))


def invite(client: TestClient, token: str, project_id: str, login: str) -> httpx2.Response:
    return client.post(
        f"/project/{project_id}/invite", params={"user": login}, headers=bearer(token)
    )


def members(client: TestClient, token: str, project_id: str) -> list[dict[str, Any]]:
    r = client.get(f"/project/{project_id}/members", headers=bearer(token))
    assert r.status_code == 200, r.text
    body: list[dict[str, Any]] = r.json()
    return body


def logins(client: TestClient, token: str, project_id: str) -> list[str]:
    return [m["login"] for m in members(client, token, project_id)]


def test_owner_removes_participant(api_client: TestClient, migrated_database_url: str) -> None:
    _, mila = signed_in(api_client)
    anna_id, anna = signed_in(api_client, "anna")
    zoe_id, zoe = signed_in(api_client, "zoe")
    created = create_project(api_client, mila)
    add_participant(migrated_database_url, created["id"], anna_id)
    add_participant(migrated_database_url, created["id"], zoe_id)

    r = remove(api_client, mila, created["id"], anna_id)

    assert r.status_code == 204
    assert r.content == b""
    info = f"/project/{created['id']}/info"
    assert api_client.get(info, headers=bearer(anna)).status_code == 404
    assert api_client.get("/projects", headers=bearer(anna)).json() == []
    assert logins(api_client, mila, created["id"]) == ["mila", "zoe"]
    assert api_client.get(info, headers=bearer(zoe)).status_code == 200


def test_participant_leaves(api_client: TestClient, migrated_database_url: str) -> None:
    _, mila = signed_in(api_client)
    anna_id, anna = signed_in(api_client, "anna")
    created = create_project(api_client, mila)
    add_participant(migrated_database_url, created["id"], anna_id)

    r = remove(api_client, anna, created["id"], anna_id)

    assert r.status_code == 204
    assert api_client.get(f"/project/{created['id']}/info", headers=bearer(anna)).status_code == 404
    assert api_client.get("/projects", headers=bearer(anna)).json() == []
    assert logins(api_client, mila, created["id"]) == ["mila"]


def test_participant_cannot_remove_others(
    api_client: TestClient, migrated_database_url: str
) -> None:
    mila_id, mila = signed_in(api_client)
    anna_id, anna = signed_in(api_client, "anna")
    zoe_id, _ = signed_in(api_client, "zoe")
    created = create_project(api_client, mila)
    add_participant(migrated_database_url, created["id"], anna_id)
    add_participant(migrated_database_url, created["id"], zoe_id)

    responses = [
        remove(api_client, anna, created["id"], zoe_id),
        remove(api_client, anna, created["id"], mila_id),
    ]

    assert [r.status_code for r in responses] == [403, 403]
    assert all(
        r.json() == {"detail": "Only the project owner can remove participants"} for r in responses
    )
    assert logins(api_client, mila, created["id"]) == ["mila", "anna", "zoe"]


def test_owner_cannot_leave(api_client: TestClient) -> None:
    mila_id, mila = signed_in(api_client)
    created = create_project(api_client, mila)

    r = remove(api_client, mila, created["id"], mila_id)

    assert r.status_code == 409
    assert r.json() == {"detail": "The owner cannot leave the project"}


def test_remove_non_participant_is_404(api_client: TestClient) -> None:
    _, mila = signed_in(api_client)
    outsider_id, _ = signed_in(api_client, "outsider")
    created = create_project(api_client, mila)

    responses = [
        remove(api_client, mila, created["id"], str(uuid4())),
        remove(api_client, mila, created["id"], outsider_id),
    ]

    assert [r.status_code for r in responses] == [404, 404]
    assert all(r.json() == {"detail": "Participant not found"} for r in responses)


def test_remove_twice_second_is_participant_not_found(
    api_client: TestClient, migrated_database_url: str
) -> None:
    _, mila = signed_in(api_client)
    anna_id, _ = signed_in(api_client, "anna")
    created = create_project(api_client, mila)
    add_participant(migrated_database_url, created["id"], anna_id)

    first = remove(api_client, mila, created["id"], anna_id)
    second = remove(api_client, mila, created["id"], anna_id)

    assert first.status_code == 204
    assert second.status_code == 404
    assert second.json() == {"detail": "Participant not found"}


def test_outsider_and_unknown_project_get_404(
    api_client: TestClient, migrated_database_url: str
) -> None:
    _, mila = signed_in(api_client)
    anna_id, anna = signed_in(api_client, "anna")
    _, outsider = signed_in(api_client, "outsider")
    created = create_project(api_client, mila)
    add_participant(migrated_database_url, created["id"], anna_id)

    responses = [
        remove(api_client, outsider, created["id"], anna_id),
        remove(api_client, mila, str(uuid4()), anna_id),
    ]

    assert [r.status_code for r in responses] == [404, 404]
    assert all(r.json() == {"detail": "Project not found"} for r in responses)
    assert responses[0].json() == responses[1].json()
    assert api_client.get(f"/project/{created['id']}/info", headers=bearer(anna)).status_code == 200


@pytest.mark.parametrize(
    "path", ["/project/not-a-uuid/members/{uid}", "/project/{pid}/members/not-a-uuid"]
)
def test_bad_ids_are_422(api_client: TestClient, path: str) -> None:
    user_id, mila = signed_in(api_client)
    created = create_project(api_client, mila)

    r = api_client.delete(path.format(uid=user_id, pid=created["id"]), headers=bearer(mila))

    assert r.status_code == 422


def test_after_leaving_project_routes_are_404(
    api_client: TestClient, migrated_database_url: str
) -> None:
    _, mila = signed_in(api_client)
    anna_id, anna = signed_in(api_client, "anna")
    signed_in(api_client, "zoe")
    created = create_project(api_client, mila)
    add_participant(migrated_database_url, created["id"], anna_id)
    pid = created["id"]
    assert remove(api_client, anna, pid, anna_id).status_code == 204

    responses = [
        remove(api_client, anna, pid, anna_id),
        invite(api_client, anna, pid, "zoe"),
        api_client.put(
            f"/project/{pid}/info", json={"name": "X", "description": ""}, headers=bearer(anna)
        ),
        api_client.get(f"/project/{pid}/members", headers=bearer(anna)),
    ]

    assert [r.status_code for r in responses] == [404, 404, 404, 404]
    assert all(r.json() == {"detail": "Project not found"} for r in responses)


def test_removed_user_can_be_invited_again(
    api_client: TestClient, migrated_database_url: str
) -> None:
    _, mila = signed_in(api_client)
    anna_id, _ = signed_in(api_client, "anna")
    created = create_project(api_client, mila)
    first = invite(api_client, mila, created["id"], "anna")
    assert first.status_code == 201
    assert remove(api_client, mila, created["id"], anna_id).status_code == 204

    second = invite(api_client, mila, created["id"], "anna")

    assert second.status_code == 201
    assert datetime.fromisoformat(second.json()["joined_at"]) > datetime.fromisoformat(
        first.json()["joined_at"]
    )


def test_remove_keeps_updated_at(api_client: TestClient, migrated_database_url: str) -> None:
    _, mila = signed_in(api_client)
    anna_id, _ = signed_in(api_client, "anna")
    created = create_project(api_client, mila)
    add_participant(migrated_database_url, created["id"], anna_id)
    path = f"/project/{created['id']}/info"

    before = api_client.get(path, headers=bearer(mila)).json()["updated_at"]
    assert remove(api_client, mila, created["id"], anna_id).status_code == 204
    after = api_client.get(path, headers=bearer(mila)).json()["updated_at"]

    assert before == after
