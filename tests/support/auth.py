import httpx2
from fastapi.testclient import TestClient


def register(
    client: TestClient, login: str = "mila", password: str = "correct-horse-1"
) -> httpx2.Response:
    return client.post(
        "/auth", json={"login": login, "password": password, "repeat_password": password}
    )


def login(client: TestClient, login: str = "mila", password: str = "correct-horse-1") -> str:
    r = client.post("/login", json={"login": login, "password": password})
    assert r.status_code == 200, r.text
    return str(r.json()["access_token"])


def bearer(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def signed_in(client: TestClient, login: str = "mila") -> tuple[str, str]:
    password = "correct-horse-1"
    registered = register(client, login, password)
    assert registered.status_code == 201, registered.text
    r = client.post("/login", json={"login": login, "password": password})
    assert r.status_code == 200, r.text
    return str(registered.json()["id"]), str(r.json()["access_token"])
