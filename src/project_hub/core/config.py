from typing import Literal

from pydantic import SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict

DbBackend = Literal["orm", "sql"]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="APP_", env_file=".env", extra="ignore")

    name: str = "Project Hub"
    debug: bool = False
    db_backend: DbBackend = "orm"
    database_url: SecretStr | None = None
