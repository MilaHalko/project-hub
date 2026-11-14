from typing import Any

import psycopg
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


def add_participant(database_url: str, project_id: str, user_id: str) -> None:
    with psycopg.connect(database_url) as conn:
        conn.execute(
            "INSERT INTO project_members (project_id, user_id) VALUES (%s, %s)",
            (project_id, user_id),
        )
