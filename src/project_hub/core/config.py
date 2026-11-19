from typing import Annotated, Any, Literal
from urllib.parse import urlsplit

from pydantic import Field, SecretStr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

DbBackend = Literal["orm", "sql"]
MailBackend = Literal["smtp", "ses"]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="APP_",
        env_file=".env",
        extra="ignore",
        hide_input_in_errors=True,
    )

    name: str = "Project Hub"
    debug: bool = False
    db_backend: DbBackend = "orm"
    database_url: SecretStr | None = None
    jwt_secret: SecretStr | None = None
    s3_bucket: str | None = None
    s3_endpoint_url: str | None = None
    s3_region: str = "eu-west-1"
    mail_backend: MailBackend = "smtp"
    ses_region: str = "eu-west-1"
    smtp_host: str | None = None
    smtp_port: int = Field(default=25, ge=1, le=65535)
    mail_from: Annotated[str, Field(pattern=r"^[^@\s]+@[^@\s]+$")] = "noreply@project-hub.test"
    public_url: str | None = None
    web_url: str | None = None
    document_max_bytes: int = Field(default=10_485_760, ge=1, le=104_857_600)
    document_max_files: int = Field(default=10, ge=1, le=100)
    project_max_bytes: int = Field(default=52_428_800, ge=1, le=10_737_418_240)
    login_max_failures: int = Field(default=5, ge=1, le=1000)
    login_ip_max_failures: int = Field(default=20, ge=1, le=100_000)
    login_window_seconds: int = Field(default=900, ge=1, le=86_400)

    @field_validator(
        "jwt_secret",
        "s3_bucket",
        "s3_endpoint_url",
        "smtp_host",
        "public_url",
        "web_url",
        mode="before",
    )
    @classmethod
    def _blank_is_unset(cls, value: Any) -> Any:
        return None if isinstance(value, str) and value.strip() == "" else value

    @field_validator("jwt_secret")
    @classmethod
    def _secret_is_long_enough(cls, value: SecretStr | None) -> SecretStr | None:
        if value is not None and len(value.get_secret_value()) < 32:
            raise ValueError("jwt_secret must be at least 32 characters")
        return value

    @field_validator("public_url", "web_url")
    @classmethod
    def _is_a_base_url(cls, value: str | None) -> str | None:
        if value is None:
            return None
        parts = urlsplit(value)
        if (
            parts.scheme not in ("http", "https")
            or not parts.hostname
            or any(c.isspace() for c in value)
            or "?" in value
            or "#" in value
        ):
            raise ValueError("must be an http(s) URL with a host, without a query or fragment")
        return value.rstrip("/")
