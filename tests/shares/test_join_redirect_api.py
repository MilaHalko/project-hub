from collections.abc import Callable
from urllib.parse import parse_qs, urlsplit

import pytest
from fastapi.testclient import TestClient

from tests.support.auth import signed_in
from tests.support.mail import random_address
from tests.support.projects import create_project
from tests.support.shares import join, shared_token

BROWSER = {"Accept": "text/html,application/xhtml+xml"}


@pytest.fixture
def web_client(make_api_client: Callable[..., TestClient]) -> TestClient:
    return make_api_client(web_url="http://web.test")


def test_browser_without_a_sign_in_is_sent_to_the_web_app_and_the_link_stays_pending(
    web_client: TestClient, mailpit_url: str
) -> None:
    _, mila = signed_in(web_client)
    _, anna = signed_in(web_client, "anna")
    created = create_project(web_client, mila)
    token = shared_token(web_client, mailpit_url, mila, created["id"], random_address())

    r = web_client.get("/join", params={"token": token}, headers=BROWSER, follow_redirects=False)

    assert r.status_code == 303
    assert r.headers["location"] == f"http://web.test/join?token={token}"
    assert r.headers["cache-control"] == "no-store"
    assert join(web_client, token, anna).status_code == 200


def test_odd_token_is_encoded_and_the_target_stays_the_web_origin(
    web_client: TestClient,
) -> None:
    token = "a b&next=//evil.example"

    r = web_client.get("/join", params={"token": token}, headers=BROWSER, follow_redirects=False)

    assert r.status_code == 303
    target = urlsplit(r.headers["location"])
    assert target.netloc == "web.test"
    assert target.path == "/join"
    assert parse_qs(target.query) == {"token": [token]}


@pytest.mark.parametrize(
    "headers",
    [
        {"Accept": "application/json"},
        {},
        {"Authorization": "Bearer garbage", "Accept": "text/html"},
        {"Authorization": "Basic eDp5", "Accept": "text/html"},
    ],
)
def test_other_requests_get_401_even_with_a_web_url(
    web_client: TestClient, headers: dict[str, str]
) -> None:
    r = join(web_client, "x" * 43, headers=headers)
    assert r.status_code == 401
    assert r.headers["www-authenticate"] == "Bearer"


def test_without_a_web_url_a_browser_gets_401(api_client: TestClient) -> None:
    r = api_client.get("/join", params={"token": "x" * 43}, headers=BROWSER, follow_redirects=False)
    assert r.status_code == 401


def test_signed_in_browser_joins_instead_of_being_redirected(
    web_client: TestClient, mailpit_url: str
) -> None:
    _, mila = signed_in(web_client)
    _, anna = signed_in(web_client, "anna")
    created = create_project(web_client, mila)
    token = shared_token(web_client, mailpit_url, mila, created["id"], random_address())

    r = join(web_client, token, anna, headers={"Accept": "text/html"})

    assert r.status_code == 200
