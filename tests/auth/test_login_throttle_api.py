import logging
from collections.abc import Callable

import httpx2
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from project_hub.auth.throttle import LoginThrottle
from project_hub.core.config import Settings
from tests.support.auth import login, register

BLOCKED = {"detail": "Too many failed login attempts. Try again later."}
MAX_LOGIN_FAILURES = 3
MAX_IP_FAILURES = 5
WINDOW_SECONDS = 900


class FakeClock:
    def __init__(self) -> None:
        self.now = 1000.0

    def __call__(self) -> float:
        return self.now

    def advance(self, seconds: float) -> None:
        self.now += seconds


@pytest.fixture
def clock() -> FakeClock:
    return FakeClock()


@pytest.fixture
def client(make_api_client: Callable[..., TestClient], clock: FakeClock) -> TestClient:
    c = make_api_client(
        login_max_failures=MAX_LOGIN_FAILURES,
        login_ip_max_failures=MAX_IP_FAILURES,
        login_window_seconds=WINDOW_SECONDS,
    )
    app = c.app
    assert isinstance(app, FastAPI)
    settings: Settings = app.state.settings
    app.state.login_throttle = LoginThrottle.from_settings(settings, clock)
    return c


def _attempt(
    client: TestClient, user: str = "mila", password: str = "wrong-pass-99"
) -> httpx2.Response:
    return client.post("/login", json={"login": user, "password": password})


def _from_ip(client: TestClient, ip: str) -> TestClient:
    app = client.app
    assert isinstance(app, FastAPI)
    return TestClient(app, client=(ip, 50000))


def test_failures_past_the_limit_get_429_with_retry_after(client: TestClient) -> None:
    register(client)
    for _ in range(MAX_LOGIN_FAILURES):
        assert _attempt(client).status_code == 401
    blocked = _attempt(client)
    assert blocked.status_code == 429
    assert blocked.json() == BLOCKED
    assert blocked.headers["retry-after"] == str(WINDOW_SECONDS)


def test_right_password_is_refused_until_the_window_passes(
    client: TestClient, clock: FakeClock
) -> None:
    register(client)
    for _ in range(MAX_LOGIN_FAILURES):
        _attempt(client)

    clock.advance(WINDOW_SECONDS - 1)
    still_blocked = _attempt(client, password="correct-horse-1")
    assert still_blocked.status_code == 429
    assert still_blocked.headers["retry-after"] == "1"

    clock.advance(1)
    assert _attempt(client, password="correct-horse-1").status_code == 200


def test_blocked_attempts_do_not_extend_the_block(client: TestClient, clock: FakeClock) -> None:
    register(client)
    for _ in range(MAX_LOGIN_FAILURES):
        _attempt(client)
    clock.advance(WINDOW_SECONDS - 1)
    assert _attempt(client).status_code == 429
    clock.advance(1)
    assert _attempt(client, password="correct-horse-1").status_code == 200


def test_failures_older_than_the_window_do_not_count(client: TestClient, clock: FakeClock) -> None:
    register(client)
    for _ in range(MAX_LOGIN_FAILURES - 1):
        _attempt(client)
    clock.advance(WINDOW_SECONDS)
    for _ in range(MAX_LOGIN_FAILURES):
        assert _attempt(client).status_code == 401
    assert _attempt(client).status_code == 429


def test_a_success_resets_the_login_counter(client: TestClient) -> None:
    register(client)
    for _ in range(MAX_LOGIN_FAILURES - 1):
        _attempt(client)
    login(client)
    for _ in range(MAX_LOGIN_FAILURES):
        assert _attempt(client).status_code == 401
    assert _attempt(client).status_code == 429


def test_a_blocked_login_does_not_block_other_logins(client: TestClient) -> None:
    register(client)
    register(client, login="olga")
    for _ in range(MAX_LOGIN_FAILURES):
        _attempt(client)
    assert _attempt(client).status_code == 429
    assert _attempt(client, user="olga", password="correct-horse-1").status_code == 200


def test_an_unknown_login_is_blocked_just_like_a_known_one(client: TestClient) -> None:
    for _ in range(MAX_LOGIN_FAILURES):
        assert _attempt(client, user="ghost").status_code == 401
    blocked = _attempt(client, user="ghost")
    assert blocked.status_code == 429
    assert blocked.json() == BLOCKED


def test_one_ip_is_blocked_after_too_many_failures_across_logins(client: TestClient) -> None:
    register(client)
    attacker = _from_ip(client, "203.0.113.7")
    for n in range(MAX_IP_FAILURES):
        assert _attempt(attacker, user=f"ghost{n}").status_code == 401
    blocked = _attempt(attacker, password="correct-horse-1")
    assert blocked.status_code == 429
    assert blocked.json() == BLOCKED
    assert blocked.headers["retry-after"] == str(WINDOW_SECONDS)

    elsewhere = _from_ip(client, "203.0.113.8")
    assert _attempt(elsewhere, password="correct-horse-1").status_code == 200


def test_the_ip_block_ends_with_the_window(client: TestClient, clock: FakeClock) -> None:
    register(client)
    attacker = _from_ip(client, "203.0.113.7")
    for n in range(MAX_IP_FAILURES):
        _attempt(attacker, user=f"ghost{n}")
    clock.advance(WINDOW_SECONDS)
    assert _attempt(attacker, password="correct-horse-1").status_code == 200


def test_a_success_does_not_use_up_the_ip_allowance(client: TestClient) -> None:
    register(client)
    for _ in range(MAX_IP_FAILURES * 2):
        assert _attempt(client, password="correct-horse-1").status_code == 200
    for n in range(MAX_IP_FAILURES):
        assert _attempt(client, user=f"ghost{n}").status_code == 401
    assert _attempt(client, user="ghost-last").status_code == 429


def test_failed_and_blocked_attempts_are_logged_with_masked_login_and_ip(
    client: TestClient, caplog: pytest.LogCaptureFixture
) -> None:
    register(client)
    attacker = _from_ip(client, "203.0.113.7")
    caplog.clear()
    with caplog.at_level(logging.INFO, logger="project_hub.auth.service"):
        for _ in range(MAX_LOGIN_FAILURES + 1):
            _attempt(attacker)

    events = [
        (r.__dict__["event"], r.__dict__["ip"])
        for r in caplog.records
        if r.name.endswith("service")
    ]
    assert events == [("login failed", "203.0.113.7")] * MAX_LOGIN_FAILURES + [
        ("login blocked", "203.0.113.7")
    ]
    blocked = caplog.records[-1]
    assert blocked.__dict__["login"] == "mi***"
    assert "mila" not in blocked.getMessage()
    assert "wrong-pass-99" not in str(blocked.__dict__)
