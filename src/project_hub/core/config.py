from typing import Any, Literal

from pydantic import SecretStr, field_validator
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

    @field_validator("jwt_secret", mode="before")
    @classmethod
    def _blank_secret_is_unset(cls, value: Any) -> Any:
        return None if isinstance(value, str) and value.strip() == "" else value

    @field_validator("jwt_secret")
    @classmethod
    def _secret_is_long_enough(cls, value: SecretStr | None) -> SecretStr | None:
        if value is not None and len(value.get_secret_value()) < 32:
            raise ValueError("jwt_secret must be at least 32 characters")
        return value
