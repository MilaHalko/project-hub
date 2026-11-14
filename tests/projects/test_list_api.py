import pytest
from fastapi.testclient import TestClient

from tests.support.auth import bearer, signed_in
from tests.support.projects import add_participant, create_project


def test_empty_list(api_client: TestClient) -> None:
    _, token = signed_in(api_client)

    r = api_client.get("/projects", headers=bearer(token))

    assert r.status_code == 200
    assert r.json() == []


def test_lists_owned_and_shared_with_roles_and_documents(
    api_client: TestClient, migrated_database_url: str
) -> None:
    mila_id, mila = signed_in(api_client)
    _, anna = signed_in(api_client, "anna")
    first = create_project(api_client, mila, "First")
    second = create_project(api_client, mila, "Second")
    shared = create_project(api_client, anna, "Shared")
    create_project(api_client, anna, "Private")
    add_participant(migrated_database_url, shared["id"], mila_id)

    r = api_client.get("/projects", headers=bearer(mila))

    assert r.status_code == 200
    by_id = {item["id"]: item for item in r.json()}
    assert by_id == {
        first["id"]: {**first, "documents": []},
        second["id"]: {**second, "documents": []},
        shared["id"]: {**shared, "my_role": "participant", "documents": []},
    }


def test_role_filter(api_client: TestClient, migrated_database_url: str) -> None:
    mila_id, mila = signed_in(api_client)
    _, anna = signed_in(api_client, "anna")
    owned = create_project(api_client, mila, "Owned")
    shared = create_project(api_client, anna, "Shared")
    add_participant(migrated_database_url, shared["id"], mila_id)

    as_owner = api_client.get("/projects", headers=bearer(mila), params={"role": "owner"})
    as_participant = api_client.get(
        "/projects", headers=bearer(mila), params={"role": "participant"}
    )

    assert as_owner.status_code == as_participant.status_code == 200
    assert [item["id"] for item in as_owner.json()] == [owned["id"]]
    assert [item["id"] for item in as_participant.json()] == [shared["id"]]


def test_paging_has_no_overlap_or_gap(api_client: TestClient) -> None:
    _, token = signed_in(api_client)
    for i in range(5):
        create_project(api_client, token, f"P{i}")

    full = api_client.get("/projects", headers=bearer(token)).json()
    pages = [
        api_client.get("/projects", headers=bearer(token), params={"limit": 2, "offset": offset})
        for offset in (0, 2, 4)
    ]

    assert len(full) == 5
    assert [page.status_code for page in pages] == [200, 200, 200]
    assert [len(page.json()) for page in pages] == [2, 2, 1]
    assert [item for page in pages for item in page.json()] == full


def test_offset_past_end_is_empty(api_client: TestClient) -> None:
    _, token = signed_in(api_client)
    create_project(api_client, token, "First")
    create_project(api_client, token, "Second")

    r = api_client.get("/projects", headers=bearer(token), params={"offset": 50})

    assert r.status_code == 200
    assert r.json() == []


@pytest.mark.parametrize(
    "params",
    [
        pytest.param({"limit": 0}, id="limit-0"),
        pytest.param({"limit": 101}, id="limit-101"),
        pytest.param({"offset": -1}, id="offset-negative"),
        pytest.param({"offset": 100001}, id="offset-too-big"),
        pytest.param({"role": "admin"}, id="role-unknown"),
    ],
)
def test_invalid_query_is_422(api_client: TestClient, params: dict[str, str | int]) -> None:
    _, token = signed_in(api_client)

    r = api_client.get("/projects", headers=bearer(token), params=params)

    assert r.status_code == 422


@pytest.mark.parametrize(
    "params",
    [
        pytest.param({"limit": 1}, id="limit-1"),
        pytest.param({"limit": 100}, id="limit-100"),
        pytest.param({"offset": 100000}, id="offset-100000"),
    ],
)
def test_boundary_query_is_accepted(api_client: TestClient, params: dict[str, int]) -> None:
    _, token = signed_in(api_client)

    r = api_client.get("/projects", headers=bearer(token), params=params)

    assert r.status_code == 200
