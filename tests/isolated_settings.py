from pydantic_settings import SettingsConfigDict

from project_hub.core.config import Settings


class IsolatedSettings(Settings):
    """Settings that never read a .env file (tests only)."""

    model_config = SettingsConfigDict(env_file=None)
