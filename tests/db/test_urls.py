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
