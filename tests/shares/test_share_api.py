import logging
from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import uuid4

import psycopg
import pytest
from fastapi.testclient import TestClient

from project_hub.shares.tokens import hash_token
from tests.support.auth import bearer, signed_in
from tests.support.mail import messages_to, random_address
from tests.support.projects import add_participant, create_project
from tests.support.shares import LINK, closed_port, mailed_token, share

SENDER = "noreply@project-hub.test"
SUBJECT = "You are invited to a project on Project Hub"


def no_mail(mailpit_url: str, address: str) -> bool:
    return messages_to(mailpit_url, address, expect=0, timeout=1) == []


def stored_shares(database_url: str, email: str) -> list[tuple[Any, ...]]:
    with psycopg.connect(database_url) as conn:
        return conn.execute(
            "SELECT token_hash FROM project_shares WHERE email = %s", (email,)
        ).fetchall()


def test_owner_shares_and_the_mail_carries_a_join_link(
    api_client: TestClient, mailpit_url: str
) -> None:
    _, mila = signed_in(api_client)
    created = create_project(api_client, mila, name="Diploma")
    address = random_address()

    r = share(api_client, mila, created["id"], address)

    assert r.status_code == 200, r.text
    body = r.json()
    assert set(body) == {"email", "expires_at"}
    assert body["email"] == address
    expires_at = datetime.fromisoformat(body["expires_at"])
    assert abs(expires_at - (datetime.now(UTC) + timedelta(days=7))) < timedelta(minutes=1)
    (message,) = messages_to(mailpit_url, address)
    assert message["From"]["Address"] == SENDER
    assert [to["Address"] for to in message["To"]] == [address]
    assert message["Subject"] == SUBJECT
    assert "@mila" in message["Text"]
    assert "Diploma" in message["Text"]
    token = mailed_token(message)
    assert token not in r.text


def test_only_the_token_hash_is_stored_and_the_token_is_never_logged(
    api_client: TestClient,
    mailpit_url: str,
    migrated_database_url: str,
    caplog: pytest.LogCaptureFixture,
) -> None:
    _, mila = signed_in(api_client)
    created = create_project(api_client, mila)
    address = random_address()

    with caplog.at_level(logging.DEBUG):
        assert share(api_client, mila, created["id"], address).status_code == 200

    token = mailed_token(messages_to(mailpit_url, address)[0])
    assert stored_shares(migrated_database_url, address) == [(hash_token(token),)]
    with psycopg.connect(migrated_database_url) as conn:
        rows = conn.execute("SELECT * FROM project_shares").fetchall()
    assert rows
    assert not [row for row in rows if token in repr(row)]
    assert caplog.records
    assert not [r for r in caplog.records if token in r.getMessage()]


def test_participant_cannot_share(
    api_client: TestClient, mailpit_url: str, migrated_database_url: str
) -> None:
    _, mila = signed_in(api_client)
    anna_id, anna = signed_in(api_client, "anna")
    created = create_project(api_client, mila)
    add_participant(migrated_database_url, created["id"], anna_id)
    address = random_address()

    r = share(api_client, anna, created["id"], address)

    assert r.status_code == 403
    assert r.json() == {"detail": "Only the project owner can share the project"}
    assert no_mail(mailpit_url, address)


def test_outsider_and_unknown_project_get_the_same_404(
    api_client: TestClient, mailpit_url: str
) -> None:
    _, mila = signed_in(api_client)
    _, zoe = signed_in(api_client, "zoe")
    created = create_project(api_client, mila)
    first, second = random_address(), random_address()

    outsider = share(api_client, zoe, created["id"], first)
    unknown = share(api_client, mila, str(uuid4()), second)

    assert outsider.status_code == 404
    assert unknown.status_code == 404
    assert outsider.json() == {"detail": "Project not found"}
    assert unknown.content == outsider.content
    assert no_mail(mailpit_url, first)
    assert no_mail(mailpit_url, second)


@pytest.mark.parametrize(
    "case",
    [
        pytest.param("missing", id="missing"),
        pytest.param("empty", id="empty"),
        pytest.param("not-an-email", id="not-an-email"),
        pytest.param("too-long", id="255-characters"),
        pytest.param("leading-space", id="leading-space"),
        pytest.param("trailing-space", id="trailing-space"),
        pytest.param("crlf", id="crlf-header"),
        pytest.param("bad-project-id", id="bad-project-id"),
    ],
)
def test_invalid_share_request_is_422_and_sends_nothing(
    api_client: TestClient, mailpit_url: str, case: str
) -> None:
    _, mila = signed_in(api_client)
    project_id = create_project(api_client, mila)["id"]
    address, extra = random_address(), random_address()
    params: dict[str, str] = {
        "missing": {},
        "empty": {"with": ""},
        "not-an-email": {"with": "not-an-email"},
        "too-long": {"with": uuid4().hex + "a" * 211 + "@example.com"},
        "leading-space": {"with": f" {address}"},
        "trailing-space": {"with": f"{address} "},
        "crlf": {"with": f"{address}\r\nBcc: {extra}"},
        "bad-project-id": {"with": address},
    }[case]
    if case == "too-long":
        assert len(params["with"]) == 255
    if case == "bad-project-id":
        project_id = "abc"

    r = api_client.get(f"/project/{project_id}/share", params=params, headers=bearer(mila))

    assert r.status_code == 422, r.text
    assert no_mail(mailpit_url, address)
    assert no_mail(mailpit_url, extra)
    if case == "too-long":
        assert no_mail(mailpit_url, params["with"])


@pytest.mark.parametrize(
    "overrides",
    [
        pytest.param({"smtp_host": None}, id="no-smtp-host"),
        pytest.param({"public_url": None}, id="no-public-url"),
    ],
)
def test_share_without_mail_settings_is_503(
    api_client: TestClient,
    make_api_client: Callable[..., TestClient],
    mailpit_url: str,
    overrides: dict[str, Any],
) -> None:
    _, mila = signed_in(api_client)
    created = create_project(api_client, mila)
    address = random_address()

    r = share(make_api_client(**overrides), mila, created["id"], address)

    assert r.status_code == 503
    assert r.json() == {"detail": "Email sharing is not configured"}
    assert no_mail(mailpit_url, address)


def test_share_is_503_and_stores_nothing_when_the_mail_cannot_be_sent(
    api_client: TestClient,
    make_api_client: Callable[..., TestClient],
    migrated_database_url: str,
) -> None:
    _, mila = signed_in(api_client)
    created = create_project(api_client, mila)
    address = random_address()
    broken = make_api_client(smtp_host="127.0.0.1", smtp_port=closed_port())

    r = share(broken, mila, created["id"], address)

    assert r.status_code == 503
    assert r.json() == {"detail": "Email could not be sent"}
    with psycopg.connect(migrated_database_url) as conn:
        assert conn.execute("SELECT count(*) FROM project_shares").fetchone() == (0,)


def test_eleventh_pending_address_is_429_until_a_link_expires(
    api_client: TestClient, mailpit_url: str, migrated_database_url: str
) -> None:
    _, mila = signed_in(api_client)
    created = create_project(api_client, mila)
    addresses = [random_address() for _ in range(10)]
    for address in addresses:
        assert share(api_client, mila, created["id"], address).status_code == 200
    eleventh = random_address()

    refused = share(api_client, mila, created["id"], eleventh)

    assert refused.status_code == 429
    assert refused.json() == {"detail": "Too many pending share links for this project"}
    assert no_mail(mailpit_url, eleventh)
    assert share(api_client, mila, created["id"], addresses[3]).status_code == 200

    with psycopg.connect(migrated_database_url) as conn:
        conn.execute(
            "UPDATE project_shares SET expires_at = now() - interval '1 second' WHERE email = %s",
            (addresses[0],),
        )

    assert share(api_client, mila, created["id"], eleventh).status_code == 200
    assert len(messages_to(mailpit_url, eleventh)) == 1


def test_second_share_to_the_same_address_replaces_the_link(
    api_client: TestClient, mailpit_url: str, migrated_database_url: str
) -> None:
    _, mila = signed_in(api_client)
    created = create_project(api_client, mila)
    address = random_address()

    assert share(api_client, mila, created["id"], address).status_code == 200
    first = mailed_token(messages_to(mailpit_url, address)[0])
    again = share(api_client, mila, created["id"], address.upper())

    assert again.status_code == 200
    assert again.json()["email"] == address
    tokens = {mailed_token(m) for m in messages_to(mailpit_url, address, expect=2)}
    assert len(tokens) == 2
    (second,) = tokens - {first}
    assert stored_shares(migrated_database_url, address) == [(hash_token(second),)]


def test_cyrillic_project_name_is_mailed(api_client: TestClient, mailpit_url: str) -> None:
    _, mila = signed_in(api_client)
    created = create_project(api_client, mila, name="Дипломна робота")
    address = random_address()

    assert share(api_client, mila, created["id"], address).status_code == 200

    (message,) = messages_to(mailpit_url, address)
    assert "Дипломна робота" in message["Text"]
    assert len(LINK.findall(message["Text"])) == 1


def test_plus_tag_and_mixed_case_address_is_answered_and_mailed_in_lower_case(
    api_client: TestClient, mailpit_url: str
) -> None:
    _, mila = signed_in(api_client)
    created = create_project(api_client, mila)
    tag = uuid4().hex
    address = f"Anna+Hub-{tag}@Example.com"

    r = share(api_client, mila, created["id"], address)

    assert r.status_code == 200, r.text
    assert r.json()["email"] == address.lower()
    (message,) = messages_to(mailpit_url, address.lower())
    assert [to["Address"] for to in message["To"]] == [address.lower()]


def test_share_does_not_change_updated_at(api_client: TestClient, mailpit_url: str) -> None:
    _, mila = signed_in(api_client)
    created = create_project(api_client, mila)

    assert share(api_client, mila, created["id"], random_address()).status_code == 200

    info = api_client.get(f"/project/{created['id']}/info", headers=bearer(mila))
    assert info.json()["updated_at"] == created["updated_at"]
