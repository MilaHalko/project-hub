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


def test_blank_s3_settings_are_unset(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("APP_S3_BUCKET", "  ")
    monkeypatch.setenv("APP_S3_ENDPOINT_URL", "")
    s = IsolatedSettings()
    assert s.s3_bucket is None
    assert s.s3_endpoint_url is None


def test_s3_settings_are_read_from_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("APP_S3_BUCKET", "project-hub-documents")
    monkeypatch.setenv("APP_S3_ENDPOINT_URL", "http://s3:5000")
    monkeypatch.setenv("APP_S3_REGION", "eu-central-1")
    s = IsolatedSettings()
    assert s.s3_bucket == "project-hub-documents"
    assert s.s3_endpoint_url == "http://s3:5000"
    assert s.s3_region == "eu-central-1"


def test_s3_region_defaults_to_eu_west_1() -> None:
    assert IsolatedSettings().s3_region == "eu-west-1"


def test_document_limits_default() -> None:
    s = IsolatedSettings()
    assert s.document_max_bytes == 10_485_760
    assert s.document_max_files == 10


@pytest.mark.parametrize(
    ("name", "value"),
    [
        ("APP_DOCUMENT_MAX_BYTES", "0"),
        ("APP_DOCUMENT_MAX_BYTES", "104857601"),
        ("APP_DOCUMENT_MAX_FILES", "0"),
        ("APP_DOCUMENT_MAX_FILES", "101"),
    ],
)
def test_document_limits_reject_out_of_range(
    monkeypatch: pytest.MonkeyPatch, name: str, value: str
) -> None:
    monkeypatch.setenv(name, value)
    with pytest.raises(ValidationError):
        IsolatedSettings()


@pytest.mark.parametrize(
    ("name", "value", "field"),
    [
        ("APP_DOCUMENT_MAX_BYTES", "1", "document_max_bytes"),
        ("APP_DOCUMENT_MAX_BYTES", "104857600", "document_max_bytes"),
        ("APP_DOCUMENT_MAX_FILES", "1", "document_max_files"),
        ("APP_DOCUMENT_MAX_FILES", "100", "document_max_files"),
    ],
)
def test_document_limits_accept_range_ends(
    monkeypatch: pytest.MonkeyPatch, name: str, value: str, field: str
) -> None:
    monkeypatch.setenv(name, value)
    assert getattr(IsolatedSettings(), field) == int(value)


def test_mail_settings_default() -> None:
    s = IsolatedSettings()
    assert s.smtp_host is None
    assert s.smtp_port == 25
    assert s.mail_from == "noreply@project-hub.test"


def test_blank_smtp_host_is_unset(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("APP_SMTP_HOST", " ")
    assert IsolatedSettings().smtp_host is None


@pytest.mark.parametrize("value", ["0", "65536"])
def test_smtp_port_rejects_out_of_range_values(monkeypatch: pytest.MonkeyPatch, value: str) -> None:
    monkeypatch.setenv("APP_SMTP_PORT", value)
    with pytest.raises(ValidationError):
        IsolatedSettings()


@pytest.mark.parametrize("value", ["noreply", "a@b\r\nBcc: c@d", "a b@c"])
def test_mail_from_rejects_malformed_addresses(monkeypatch: pytest.MonkeyPatch, value: str) -> None:
    monkeypatch.setenv("APP_MAIL_FROM", value)
    with pytest.raises(ValidationError):
        IsolatedSettings()
