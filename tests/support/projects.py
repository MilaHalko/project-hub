from typing import Any

from fastapi.testclient import TestClient

from tests.support.auth import bearer


def create_project(
    client: TestClient, token: str, name: str = "Diploma", description: str = ""
) -> dict[str, Any]:
    r = client.post(
        "/projects", headers=bearer(token), json={"name": name, "description": description}
    )
    assert r.status_code == 201, r.text
    body: dict[str, Any] = r.json()
    return body
