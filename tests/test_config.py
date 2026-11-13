from pathlib import Path

import pytest
from pydantic import ValidationError

from project_hub.core.config import Settings
from tests.isolated_settings import IsolatedSettings


def test_defaults_without_env() -> None:
    s = IsolatedSettings()
    assert s.name == "Project Hub"
    assert s.debug is False


def test_env_vars_override_defaults(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("APP_NAME", "x")
    monkeypatch.setenv("APP_DEBUG", "true")
    s = IsolatedSettings()
    assert s.name == "x"
    assert s.debug is True


def test_invalid_debug_value_raises(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("APP_DEBUG", "maybe")
    with pytest.raises(ValidationError):
        IsolatedSettings()


def test_env_file_with_unrelated_keys_is_accepted(tmp_path: Path) -> None:
    env = tmp_path / ".env"
    env.write_text("DATABASE_URL=postgres://x\nAPP_NAME=from-file\n")
    s = Settings(_env_file=env)  # pyright: ignore[reportCallIssue]
    assert s.name == "from-file"


def test_db_backend_defaults_to_orm() -> None:
    assert IsolatedSettings().db_backend == "orm"


@pytest.mark.parametrize("value", ["orm", "sql"])
def test_db_backend_accepts_known_values(monkeypatch: pytest.MonkeyPatch, value: str) -> None:
    monkeypatch.setenv("APP_DB_BACKEND", value)
    assert IsolatedSettings().db_backend == value


@pytest.mark.parametrize("value", ["sqll", "ORM", ""])
def test_db_backend_rejects_unknown_values(monkeypatch: pytest.MonkeyPatch, value: str) -> None:
    monkeypatch.setenv("APP_DB_BACKEND", value)
    with pytest.raises(ValidationError):
        IsolatedSettings()


def test_database_url_defaults_to_none() -> None:
    assert IsolatedSettings().database_url is None


def test_database_url_is_secret(monkeypatch: pytest.MonkeyPatch) -> None:
    url = "postgresql://u:s3cret@h:5432/d"
    monkeypatch.setenv("APP_DATABASE_URL", url)
    s = IsolatedSettings()
    assert s.database_url is not None
    assert s.database_url.get_secret_value() == url
    assert "s3cret" not in repr(s)
    assert "s3cret" not in str(s)


def test_jwt_secret_defaults_to_none() -> None:
    assert IsolatedSettings().jwt_secret is None


def test_empty_jwt_secret_means_not_set(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("APP_JWT_SECRET", "")
    assert IsolatedSettings().jwt_secret is None


def test_short_jwt_secret_is_rejected(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("APP_JWT_SECRET", "x" * 31)
    with pytest.raises(ValidationError):
        IsolatedSettings()


def test_jwt_secret_is_secret(monkeypatch: pytest.MonkeyPatch) -> None:
    secret = "very-private-signing-key-" + "z" * 10
    monkeypatch.setenv("APP_JWT_SECRET", secret)
    s = IsolatedSettings()
    assert s.jwt_secret is not None
    assert s.jwt_secret.get_secret_value() == secret
    assert secret not in repr(s)
    assert secret not in str(s)


def test_whitespace_only_jwt_secret_means_not_set(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("APP_JWT_SECRET", "   ")
    assert IsolatedSettings().jwt_secret is None


def test_short_jwt_secret_error_does_not_print_the_secret(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    secret = "mistyped-real-secret-value-31ch"
    assert len(secret) == 31
    monkeypatch.setenv("APP_JWT_SECRET", secret)
    with pytest.raises(ValidationError) as exc_info:
        IsolatedSettings()
    assert secret not in str(exc_info.value)
