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
