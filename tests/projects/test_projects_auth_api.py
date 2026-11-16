from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from tests.support.auth import bearer


@pytest.mark.parametrize(
    ("method", "path"),
    [
        pytest.param("POST", "/projects", id="create"),
        pytest.param("GET", f"/project/{uuid4()}/info", id="info"),
        pytest.param("GET", "/projects", id="list"),
        pytest.param("PUT", f"/project/{uuid4()}/info", id="update"),
        pytest.param("DELETE", f"/project/{uuid4()}", id="delete"),
        pytest.param("GET", f"/project/{uuid4()}/members", id="members"),
        pytest.param("POST", f"/project/{uuid4()}/invite?user=anna", id="invite"),
        pytest.param("DELETE", f"/project/{uuid4()}/members/{uuid4()}", id="remove-member"),
        pytest.param("GET", f"/project/{uuid4()}/share?with=a@example.com", id="share"),
    ],
)
@pytest.mark.parametrize(
    "headers",
    [pytest.param({}, id="no-header"), pytest.param(bearer("garbage"), id="garbage-token")],
)
def test_routes_require_token(
    api_client: TestClient, method: str, path: str, headers: dict[str, str]
) -> None:
    r = api_client.request(method, path, headers=headers, json={"name": "Diploma"})

    assert r.status_code == 401
    assert r.headers["www-authenticate"] == "Bearer"
