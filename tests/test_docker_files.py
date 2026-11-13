"""Fast file checks for the Docker setup; the image smoke tests are opt-in (``-m docker``)."""

import tomllib
from pathlib import Path
from typing import Any

import pytest

from tests.support.docker import compose_config as render_compose_config

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture(scope="module")
def compose_config() -> dict[str, Any]:
    """Render ``docker compose config`` once for all compose tests in this module."""
    return render_compose_config()


def test_dockerfile_pins_poetry() -> None:
    assert "poetry==2.5.1" in (ROOT / "Dockerfile").read_text(encoding="utf-8")


def test_dockerfile_poetry_install_is_non_interactive() -> None:
    lines = (ROOT / "Dockerfile").read_text(encoding="utf-8").splitlines()
    installs = [line for line in lines if "poetry install" in line]
    assert installs
    assert all("--no-interaction" in line for line in installs)


def test_dockerignore_excludes_venv_and_env() -> None:
    lines = [
        line.strip() for line in (ROOT / ".dockerignore").read_text(encoding="utf-8").splitlines()
    ]
    assert ".venv/" in lines
    assert ".env" in lines


def test_compose_config_is_valid(compose_config: dict[str, Any]) -> None:
    services = compose_config["services"]
    assert {"db", "api"} <= services.keys()


def test_compose_db_has_healthcheck(compose_config: dict[str, Any]) -> None:
    db = compose_config["services"]["db"]
    assert "pg_isready" in " ".join(db["healthcheck"]["test"])


def test_compose_api_waits_for_healthy_db(compose_config: dict[str, Any]) -> None:
    api = compose_config["services"]["api"]
    assert api["depends_on"]["db"]["condition"] == "service_healthy"


def test_compose_runs_migrations_before_api(compose_config: dict[str, Any]) -> None:
    services = compose_config["services"]
    migrate, api = services["migrate"], services["api"]
    assert migrate["command"] == ["python", "-m", "project_hub.db.migrate"]
    assert migrate["depends_on"]["db"]["condition"] == "service_healthy"
    assert api["depends_on"]["migrate"]["condition"] == "service_completed_successfully"
    assert migrate["environment"]["APP_DATABASE_URL"] == api["environment"]["APP_DATABASE_URL"]


def test_compose_db_default_host_port_is_55433(compose_config: dict[str, Any]) -> None:
    db = compose_config["services"]["db"]
    assert db["ports"][0]["published"] == "55433"


def test_compose_ports_bind_loopback_only(compose_config: dict[str, Any]) -> None:
    services = compose_config["services"]
    for name in ("db", "api"):
        assert services[name]["ports"][0]["host_ip"] == "127.0.0.1"


def test_compose_has_no_fixed_project_name() -> None:
    lines = (ROOT / "docker-compose.yml").read_text(encoding="utf-8").splitlines()
    assert not any(line.startswith("name:") for line in lines)


def test_docker_marker_is_opt_in() -> None:
    pytest_options = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))["tool"][
        "pytest"
    ]["ini_options"]
    assert '-m "not docker"' in pytest_options["addopts"]
    assert any(marker.startswith("docker:") for marker in pytest_options["markers"])


def test_compose_forwards_db_backend() -> None:
    default = render_compose_config()
    assert default["services"]["api"]["environment"]["APP_DB_BACKEND"] == "orm"
    sql = render_compose_config({"APP_DB_BACKEND": "sql"})
    assert sql["services"]["api"]["environment"]["APP_DB_BACKEND"] == "sql"
