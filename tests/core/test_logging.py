import logging
import subprocess
import sys

import pytest

from project_hub.main import create_app
from tests.isolated_settings import IsolatedSettings

_SCRIPT = """
import logging
import logging.config

import uvicorn.config

from project_hub.main import create_app
from tests.isolated_settings import IsolatedSettings

logging.config.dictConfig(uvicorn.config.LOGGING_CONFIG)  # what uvicorn does before the app
create_app(IsolatedSettings())
create_app(IsolatedSettings())
logging.getLogger("project_hub.auth.service").info("security event reached the log")
"""


def test_info_records_reach_stderr_under_uvicorn_logging() -> None:
    result = subprocess.run(
        [sys.executable, "-c", _SCRIPT], capture_output=True, text=True, check=True, timeout=60
    )
    assert result.stderr.count("security event reached the log") == 1
    assert "INFO project_hub.auth.service: security event reached the log" in result.stderr


def test_missing_jwt_secret_logs_a_startup_warning(caplog: pytest.LogCaptureFixture) -> None:
    with caplog.at_level(logging.WARNING, logger="project_hub.main"):
        create_app(IsolatedSettings())
    messages = [r.getMessage() for r in caplog.records if r.name == "project_hub.main"]
    assert messages == ["APP_JWT_SECRET is not set; login is disabled"]


def test_configured_jwt_secret_logs_no_warning(caplog: pytest.LogCaptureFixture) -> None:
    with caplog.at_level(logging.WARNING, logger="project_hub.main"):
        create_app(IsolatedSettings(jwt_secret="s" * 32))  # pyright: ignore[reportArgumentType]
    assert [r for r in caplog.records if r.name == "project_hub.main"] == []
