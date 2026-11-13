import logging
from typing import Annotated

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from pydantic import BaseModel, Field

from project_hub.core.exceptions import (
    AuthenticationError,
    ConflictError,
    DomainError,
    NotFoundError,
    PermissionDeniedError,
)
from project_hub.main import create_app
from tests.isolated_settings import IsolatedSettings


class SecretBody(BaseModel):
    value: Annotated[str, Field(min_length=10)]


class ProjectNotFound(NotFoundError):
    """Feature-specific subclass used to check status inheritance."""


@pytest.fixture
def error_client() -> TestClient:
    app: FastAPI = create_app(IsolatedSettings())

    @app.get("/raise/{kind}")
    async def raise_error(kind: str) -> None:
        errors: dict[str, Exception] = {
            "not_found": NotFoundError("nope"),
            "permission": PermissionDeniedError("nope"),
            "conflict": ConflictError("nope"),
            "auth": AuthenticationError("nope"),
            "subclass": ProjectNotFound("missing"),
            "plain": DomainError("bad"),
            "unhandled": RuntimeError("secret-internal-detail"),
        }
        raise errors[kind]

    @app.get("/sync")
    def sync_route() -> None:
        raise NotFoundError("x")

    @app.get("/echo")
    def echo(n: int) -> dict[str, int]:
        return {"n": n}

    @app.post("/echo-secret")
    def echo_secret(body: SecretBody) -> dict[str, str]:
        return {"value": body.value}

    return TestClient(app, raise_server_exceptions=False)


@pytest.mark.parametrize(
    ("kind", "status"),
    [("not_found", 404), ("permission", 403), ("conflict", 409), ("auth", 401)],
)
def test_domain_error_maps_to_status(error_client: TestClient, kind: str, status: int) -> None:
    r = error_client.get(f"/raise/{kind}")
    assert r.status_code == status
    assert r.json() == {"detail": "nope"}
    assert r.headers["content-type"] == "application/json"


def test_domain_error_from_sync_route(error_client: TestClient) -> None:
    r = error_client.get("/sync")
    assert r.status_code == 404
    assert r.json() == {"detail": "x"}


def test_subclass_gets_parent_status(error_client: TestClient) -> None:
    r = error_client.get("/raise/subclass")
    assert r.status_code == 404
    assert r.json() == {"detail": "missing"}


def test_plain_domain_error_is_400(error_client: TestClient) -> None:
    r = error_client.get("/raise/plain")
    assert r.status_code == 400
    assert r.json() == {"detail": "bad"}


def test_authentication_error_sets_www_authenticate(error_client: TestClient) -> None:
    r = error_client.get("/raise/auth")
    assert r.headers["www-authenticate"] == "Bearer"


def test_unhandled_error_is_json_500(error_client: TestClient) -> None:
    r = error_client.get("/raise/unhandled")
    assert r.status_code == 500
    assert r.json() == {"detail": "Internal Server Error"}
    assert "secret-internal-detail" not in r.text


def test_unhandled_error_is_logged(
    error_client: TestClient, caplog: pytest.LogCaptureFixture
) -> None:
    with caplog.at_level(logging.ERROR, logger="project_hub.core.error_handlers"):
        error_client.get("/raise/unhandled")
    records = [
        rec
        for rec in caplog.records
        if rec.name == "project_hub.core.error_handlers" and rec.levelno == logging.ERROR
    ]
    assert records
    assert records[0].exc_info is not None


def test_validation_error_unchanged(error_client: TestClient) -> None:
    r = error_client.get("/echo", params={"n": "abc"})
    assert r.status_code == 422
    assert isinstance(r.json()["detail"], list)


def test_validation_error_does_not_echo_input(error_client: TestClient) -> None:
    r = error_client.post("/echo-secret", json={"value": "s3cr3t"})
    assert r.status_code == 422
    assert "s3cr3t" not in r.text
    assert r.json()["detail"][0]["loc"] == ["body", "value"]
