import httpx2
from fastapi.testclient import TestClient


def register(
    client: TestClient, login: str = "mila", password: str = "correct-horse-1"
) -> httpx2.Response:
    return client.post(
        "/auth", json={"login": login, "password": password, "repeat_password": password}
    )
