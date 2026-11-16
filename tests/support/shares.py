import re
import socket
from typing import Any

import httpx2
from fastapi.testclient import TestClient

from tests.support.auth import bearer
from tests.support.mail import messages_to

LINK = re.compile(r"http://testserver/join\?token=([A-Za-z0-9_-]{43})")


def share(client: TestClient, token: str, project_id: str, address: str) -> httpx2.Response:
    return client.get(
        f"/project/{project_id}/share", params={"with": address}, headers=bearer(token)
    )


def mailed_token(message: dict[str, Any]) -> str:
    (token,) = LINK.findall(message["Text"])
    return str(token)


def shared_token(
    client: TestClient, mailpit_url: str, owner: str, project_id: str, address: str
) -> str:
    r = share(client, owner, project_id, address)
    assert r.status_code == 200, r.text
    (message,) = messages_to(mailpit_url, address)
    return mailed_token(message)


def join(
    client: TestClient, token: str, user: str | None = None, headers: dict[str, str] | None = None
) -> httpx2.Response:
    return client.get("/join", params={"token": token}, headers=bearer(user) if user else headers)


def closed_port() -> int:
    with socket.socket() as closed:
        closed.bind(("127.0.0.1", 0))
        port: int = closed.getsockname()[1]
    return port
