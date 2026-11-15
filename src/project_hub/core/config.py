from typing import Any, Literal

from pydantic import Field, SecretStr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

DbBackend = Literal["orm", "sql"]


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
    document_max_bytes: int = Field(default=10_485_760, ge=1, le=104_857_600)
    document_max_files: int = Field(default=10, ge=1, le=100)

    @field_validator("jwt_secret", "s3_bucket", "s3_endpoint_url", mode="before")
    @classmethod
    def _blank_is_unset(cls, value: Any) -> Any:
        return None if isinstance(value, str) and value.strip() == "" else value

    @field_validator("jwt_secret")
    @classmethod
    def _secret_is_long_enough(cls, value: SecretStr | None) -> SecretStr | None:
        if value is not None and len(value.get_secret_value()) < 32:
            raise ValueError("jwt_secret must be at least 32 characters")
        return value
