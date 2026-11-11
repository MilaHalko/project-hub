from collections.abc import Callable

import pytest

from project_hub.db.urls import psycopg_url, sqlalchemy_url


@pytest.mark.parametrize(
    ("url", "expected"),
    [
        ("postgresql://u:p@h:5432/d", "postgresql+psycopg://u:p@h:5432/d"),
        ("postgres://u:p@h:5432/d", "postgresql+psycopg://u:p@h:5432/d"),
        ("postgresql+psycopg://u:p@h:5432/d", "postgresql+psycopg://u:p@h:5432/d"),
    ],
)
def test_sqlalchemy_url(url: str, expected: str) -> None:
    assert sqlalchemy_url(url) == expected


def test_sqlalchemy_url_rejects_other_schemes() -> None:
    with pytest.raises(ValueError):
        sqlalchemy_url("mysql://h/d")


@pytest.mark.parametrize(
    ("url", "expected"),
    [
        ("postgresql://u:p@h:5432/d", "postgresql://u:p@h:5432/d"),
        ("postgres://u:p@h:5432/d", "postgresql://u:p@h:5432/d"),
        ("postgresql+psycopg://u:p@h:5432/d", "postgresql://u:p@h:5432/d"),
    ],
)
def test_psycopg_url(url: str, expected: str) -> None:
    assert psycopg_url(url) == expected


def test_psycopg_url_rejects_other_schemes() -> None:
    with pytest.raises(ValueError) as excinfo:
        psycopg_url("mysql://u:secret@h/d")
    assert "secret" not in str(excinfo.value)


_MALFORMED_URLS = [
    ("postgresql://u:leak-check-pw@[::1/x", "leak-check-pw"),
    ("postgresql://u:pw%zz@127.0.0.1:1/x", "pw%zz"),
    ("postgresql+psycopg://u:leak-check-pw@[::1/x", "leak-check-pw"),
]


@pytest.mark.parametrize("convert", [psycopg_url, sqlalchemy_url])
@pytest.mark.parametrize(("url", "password"), _MALFORMED_URLS)
def test_malformed_url_is_rejected_without_echoing_it(
    convert: Callable[[str], str], url: str, password: str
) -> None:
    with pytest.raises(ValueError) as excinfo:
        convert(url)
    message = str(excinfo.value)
    assert password not in message
    assert url not in message


def test_psycopg_url_rejects_missing_scheme() -> None:
    with pytest.raises(ValueError):
        psycopg_url("u:secret@h/d")
