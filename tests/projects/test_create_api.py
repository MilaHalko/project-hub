from typing import Any

import psycopg
import pytest
from fastapi.testclient import TestClient

from tests.projects.invalid_bodies import INVALID_BODIES
from tests.support.auth import bearer, signed_in
from tests.support.projects import create_project


def _project_count(url: str) -> int:
    with psycopg.connect(url) as conn:
        row = conn.execute("SELECT count(*) FROM projects").fetchone()
    assert row is not None
    return int(row[0])


def test_create_returns_project_owned_by_caller(api_client: TestClient) -> None:
    user_id, token = signed_in(api_client)

    r = api_client.post(
        "/projects",
        headers=bearer(token),
        json={"name": "Diploma", "description": "Final project"},
    )

    assert r.status_code == 201
    body = r.json()
    assert body["name"] == "Diploma"
    assert body["description"] == "Final project"
    assert body["owner"] == {"id": user_id, "login": "mila"}
    assert body["my_role"] == "owner"
    assert body["created_at"] == body["updated_at"]
    assert set(body) == {
        "id",
        "name",
        "description",
        "owner",
        "my_role",
        "created_at",
        "updated_at",
    }


def test_create_without_description_defaults_to_empty(api_client: TestClient) -> None:
    _, token = signed_in(api_client)

    r = api_client.post("/projects", headers=bearer(token), json={"name": "Diploma"})

    assert r.status_code == 201
    assert r.json()["description"] == ""


def test_create_strips_name(api_client: TestClient) -> None:
    _, token = signed_in(api_client)

    body = create_project(api_client, token, name="  Diploma  ")

    assert body["name"] == "Diploma"


@pytest.mark.parametrize("payload", INVALID_BODIES)
def test_create_invalid_body_is_422(
    api_client: TestClient, migrated_database_url: str, payload: dict[str, Any]
) -> None:
    _, token = signed_in(api_client)

    r = api_client.post("/projects", headers=bearer(token), json=payload)

    assert r.status_code == 422
    assert _project_count(migrated_database_url) == 0


def test_create_description_with_nul_names_the_description(api_client: TestClient) -> None:
    _, token = signed_in(api_client)

    r = api_client.post(
        "/projects", headers=bearer(token), json={"name": "ok", "description": "a\x00b"}
    )

    assert r.status_code == 422
    assert [(e["loc"], e["msg"]) for e in r.json()["detail"]] == [
        (["body", "description"], "Value error, Description must not contain NUL characters")
    ]


def test_create_keeps_description_newlines_and_tabs(api_client: TestClient) -> None:
    _, token = signed_in(api_client)

    body = create_project(api_client, token, description="line 1\n\tline 2")

    assert body["description"] == "line 1\n\tline 2"


def test_duplicate_names_allowed(api_client: TestClient) -> None:
    _, token = signed_in(api_client)

    first = create_project(api_client, token)
    second = create_project(api_client, token)

    assert first["name"] == second["name"] == "Diploma"
    assert first["id"] != second["id"]


@pytest.mark.parametrize(
    "payload",
    [
        pytest.param({"name": 123}, id="name-int"),
        pytest.param({"name": "ok", "description": None}, id="description-null"),
    ],
)
def test_create_wrong_types_is_422(api_client: TestClient, payload: dict[str, Any]) -> None:
    _, token = signed_in(api_client)

    r = api_client.post("/projects", headers=bearer(token), json=payload)

    assert r.status_code == 422


@pytest.mark.parametrize("name", ["Дипломный проект 🎓", "я" * 100])
def test_create_accepts_unicode_name(api_client: TestClient, name: str) -> None:
    _, token = signed_in(api_client)

    body = create_project(api_client, token, name=name)

    assert body["name"] == name


def test_name_edge_whitespace_stripped_inner_control_rejected(api_client: TestClient) -> None:
    _, token = signed_in(api_client)

    body = create_project(api_client, token, name="\tDiploma\n")
    r = api_client.post("/projects", headers=bearer(token), json={"name": "Dip\nloma"})

    assert body["name"] == "Diploma"
    assert r.status_code == 422
