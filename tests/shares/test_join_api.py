from typing import Any
from uuid import UUID

import httpx2
import psycopg
import pytest
from fastapi.testclient import TestClient

from project_hub.projects.repository_orm import OrmProjectRepository
from project_hub.projects.repository_sql import SqlProjectRepository
from project_hub.shares.tokens import new_token
from tests.support.auth import bearer, signed_in
from tests.support.mail import messages_to, random_address
from tests.support.projects import add_participant, create_project
from tests.support.shares import join, share, shared_token

INVALID_LINK = {"detail": "Invite link is invalid or expired"}


def assert_no_store(r: httpx2.Response) -> None:
    assert r.headers["cache-control"] == "no-store", r.headers


def test_anna_joins_as_participant_through_the_mailed_link(
    api_client: TestClient, mailpit_url: str
) -> None:
    _, mila = signed_in(api_client)
    anna_id, anna = signed_in(api_client, "anna")
    created = create_project(api_client, mila)
    token = shared_token(api_client, mailpit_url, mila, created["id"], random_address())

    r = join(api_client, token, anna)

    assert r.status_code == 200, r.text
    assert_no_store(r)
    body = r.json()
    assert set(body) == {"login", "already_member", "project"}
    assert body["login"] == "anna"
    assert body["already_member"] is False
    assert body["project"]["id"] == created["id"]
    assert body["project"]["my_role"] == "participant"
    info = api_client.get(f"/project/{created['id']}/info", headers=bearer(anna))
    assert info.status_code == 200
    assert body["project"] == info.json()
    members = api_client.get(f"/project/{created['id']}/members", headers=bearer(mila)).json()
    assert [(m["login"], m["role"]) for m in members if m["id"] == anna_id] == [
        ("anna", "participant")
    ]


def test_join_does_not_change_updated_at(api_client: TestClient, mailpit_url: str) -> None:
    _, mila = signed_in(api_client)
    _, anna = signed_in(api_client, "anna")
    created = create_project(api_client, mila)
    token = shared_token(api_client, mailpit_url, mila, created["id"], random_address())

    r = join(api_client, token, anna)

    assert r.status_code == 200, r.text
    assert r.json()["project"]["updated_at"] == created["updated_at"]
    info = api_client.get(f"/project/{created['id']}/info", headers=bearer(mila))
    assert info.json()["updated_at"] == created["updated_at"]


def test_used_link_is_404_and_gives_no_access(api_client: TestClient, mailpit_url: str) -> None:
    _, mila = signed_in(api_client)
    _, anna = signed_in(api_client, "anna")
    _, zoe = signed_in(api_client, "zoe")
    created = create_project(api_client, mila)
    token = shared_token(api_client, mailpit_url, mila, created["id"], random_address())
    assert join(api_client, token, anna).status_code == 200

    r = join(api_client, token, zoe)

    assert r.status_code == 404
    assert r.json() == INVALID_LINK
    assert_no_store(r)
    info = api_client.get(f"/project/{created['id']}/info", headers=bearer(zoe))
    assert info.status_code == 404


@pytest.mark.parametrize("case", ["never-issued", "expired", "replaced", "project-deleted"])
def test_dead_links_all_get_the_same_404(
    api_client: TestClient, mailpit_url: str, migrated_database_url: str, case: str
) -> None:
    _, mila = signed_in(api_client)
    _, anna = signed_in(api_client, "anna")
    created = create_project(api_client, mila)
    address = random_address()
    token = shared_token(api_client, mailpit_url, mila, created["id"], address)
    if case == "never-issued":
        token = new_token()
    elif case == "expired":
        with psycopg.connect(migrated_database_url) as conn:
            conn.execute(
                "UPDATE project_shares SET expires_at = now() - interval '1 second' "
                "WHERE email = %s",
                (address,),
            )
    elif case == "replaced":
        assert share(api_client, mila, created["id"], address).status_code == 200
        assert len(messages_to(mailpit_url, address, expect=2)) == 2
    else:
        deleted = api_client.delete(f"/project/{created['id']}", headers=bearer(mila))
        assert deleted.status_code == 204

    r = join(api_client, token, anna)

    assert r.status_code == 404
    assert r.json() == INVALID_LINK
    assert_no_store(r)


def test_member_who_opens_a_link_keeps_it_pending(
    api_client: TestClient, mailpit_url: str, migrated_database_url: str
) -> None:
    _, mila = signed_in(api_client)
    bob_id, bob = signed_in(api_client, "bob")
    _, anna = signed_in(api_client, "anna")
    created = create_project(api_client, mila)
    add_participant(migrated_database_url, created["id"], bob_id)
    token = shared_token(api_client, mailpit_url, mila, created["id"], random_address())

    owner = join(api_client, token, mila)
    participant = join(api_client, token, bob)
    anna_joins = join(api_client, token, anna)

    assert owner.status_code == 200, owner.text
    assert owner.json()["login"] == "mila"
    assert owner.json()["already_member"] is True
    assert owner.json()["project"]["my_role"] == "owner"
    assert participant.status_code == 200, participant.text
    assert participant.json()["login"] == "bob"
    assert participant.json()["already_member"] is True
    assert participant.json()["project"]["my_role"] == "participant"
    assert anna_joins.status_code == 200, anna_joins.text
    assert anna_joins.json()["already_member"] is False
    for r in (owner, participant, anna_joins):
        assert_no_store(r)


@pytest.mark.parametrize(
    "headers",
    [
        pytest.param({}, id="no-header"),
        pytest.param({"Accept": "text/html"}, id="no-header-html"),
        pytest.param({"Authorization": "Bearer garbage"}, id="broken-jwt"),
        pytest.param({"Authorization": "Basic eDp5"}, id="basic"),
    ],
)
def test_join_without_a_valid_jwt_is_401_and_keeps_the_link(
    api_client: TestClient, mailpit_url: str, headers: dict[str, str]
) -> None:
    _, mila = signed_in(api_client)
    _, anna = signed_in(api_client, "anna")
    created = create_project(api_client, mila)
    token = shared_token(api_client, mailpit_url, mila, created["id"], random_address())

    r = join(api_client, token, headers=headers)

    assert r.status_code == 401, r.text
    assert r.headers["www-authenticate"] == "Bearer"
    assert_no_store(r)
    assert join(api_client, token, anna).status_code == 200


@pytest.mark.parametrize(
    "params",
    [
        pytest.param({}, id="missing"),
        pytest.param({"token": ""}, id="empty"),
        pytest.param({"token": "a" * 129}, id="129-characters"),
    ],
)
def test_invalid_token_parameter_is_422(api_client: TestClient, params: dict[str, Any]) -> None:
    _, anna = signed_in(api_client, "anna")

    with_jwt = api_client.get("/join", params=params, headers=bearer(anna))
    without_jwt = api_client.get("/join", params=params)

    for r in (with_jwt, without_jwt):
        assert r.status_code == 422, r.text
        assert_no_store(r)


def test_unknown_128_character_token_is_the_plain_404(api_client: TestClient) -> None:
    _, anna = signed_in(api_client, "anna")

    r = join(api_client, "a" * 128, anna)

    assert r.status_code == 404
    assert r.json() == INVALID_LINK
    assert_no_store(r)


def test_invite_racing_the_join_answers_already_member_and_keeps_the_link(
    api_client: TestClient,
    mailpit_url: str,
    migrated_database_url: str,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _, mila = signed_in(api_client)
    anna_id, anna = signed_in(api_client, "anna")
    _, zoe = signed_in(api_client, "zoe")
    created = create_project(api_client, mila)
    token = shared_token(api_client, mailpit_url, mila, created["id"], random_address())
    raced: list[UUID] = []

    for repository in (OrmProjectRepository, SqlProjectRepository):
        original = repository.get_for_user

        async def invite_first(
            self: Any, project_id: UUID, user_id: UUID, _original: Any = original
        ) -> Any:
            if not raced and user_id == UUID(anna_id):
                raced.append(user_id)
                add_participant(migrated_database_url, str(project_id), anna_id)
                return None
            return await _original(self, project_id, user_id)

        monkeypatch.setattr(repository, "get_for_user", invite_first)

    r = join(api_client, token, anna)

    assert raced
    assert r.status_code == 200, r.text
    assert r.json()["already_member"] is True
    assert r.json()["project"]["my_role"] == "participant"
    assert_no_store(r)
    assert join(api_client, token, zoe).json()["already_member"] is False


def test_project_deleted_during_the_join_gets_the_dead_link_404(
    api_client: TestClient,
    mailpit_url: str,
    migrated_database_url: str,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _, mila = signed_in(api_client)
    anna_id, anna = signed_in(api_client, "anna")
    created = create_project(api_client, mila)
    token = shared_token(api_client, mailpit_url, mila, created["id"], random_address())
    deleted: list[UUID] = []

    for repository in (OrmProjectRepository, SqlProjectRepository):
        original = repository.get_for_user

        async def delete_first(
            self: Any, project_id: UUID, user_id: UUID, _original: Any = original
        ) -> Any:
            if not deleted and user_id == UUID(anna_id):
                deleted.append(project_id)
                with psycopg.connect(migrated_database_url) as conn:
                    conn.execute("DELETE FROM projects WHERE id = %s", (project_id,))
                return None
            return await _original(self, project_id, user_id)

        monkeypatch.setattr(repository, "get_for_user", delete_first)

    r = join(api_client, token, anna)

    assert deleted
    assert r.status_code == 404
    assert r.json() == INVALID_LINK
    assert_no_store(r)
