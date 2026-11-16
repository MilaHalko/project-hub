import logging
import subprocess
import sys
from collections.abc import Iterator

import pytest

from project_hub.core.logging import configure_logging
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


@pytest.fixture
def access_logger() -> Iterator[logging.Logger]:
    logger = logging.getLogger("uvicorn.access")
    saved = logger.filters[:]
    yield logger
    logger.filters[:] = saved


def _log_access(logger: logging.Logger, path: str) -> None:
    logger.info('%s - "%s %s HTTP/%s" %d', "127.0.0.1:5000", "GET", path, "1.1", 303)


def test_access_log_hides_join_token(
    access_logger: logging.Logger, caplog: pytest.LogCaptureFixture
) -> None:
    configure_logging()
    with caplog.at_level(logging.INFO, logger="uvicorn.access"):
        _log_access(access_logger, "/join?token=SeCrEt-123&x=1")
    message = caplog.records[-1].getMessage()
    assert "/join?token=***&x=1" in message
    assert "SeCrEt-123" not in message


def test_access_log_keeps_other_lines(
    access_logger: logging.Logger, caplog: pytest.LogCaptureFixture
) -> None:
    configure_logging()
    with caplog.at_level(logging.INFO, logger="uvicorn.access"):
        _log_access(access_logger, "/projects?limit=5")
    assert "/projects?limit=5" in caplog.records[-1].getMessage()


def test_configure_logging_twice_adds_one_filter(access_logger: logging.Logger) -> None:
    before = len(access_logger.filters)
    configure_logging()
    configure_logging()
    assert len(access_logger.filters) - before <= 1
    assert sum(type(f).__name__ == "_HideTokenFilter" for f in access_logger.filters) == 1
