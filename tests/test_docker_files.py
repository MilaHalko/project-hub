"""Fast file checks for the Docker setup; the image smoke tests are opt-in (``-m docker``)."""

import json
import os
import shutil
import subprocess
import tempfile
import tomllib
from pathlib import Path
from typing import Any, cast

ROOT = Path(__file__).resolve().parents[1]

_COMPOSE_VARIABLES = (
    "APP_PORT",
    "APP_DB_PORT",
    "POSTGRES_USER",
    "POSTGRES_PASSWORD",
    "POSTGRES_DB",
)


def _compose_config(env: dict[str, str] | None = None) -> dict[str, Any]:
    """Render ``docker compose config`` with the compose defaults.

    The compose variables are removed from the inherited environment and an empty
    ``--env-file`` replaces ``.env``, so local settings cannot change the result.
    ``env`` adds variables on top of that clean environment.
    """
    docker = shutil.which("docker")
    assert docker is not None
    full_env = {k: v for k, v in os.environ.items() if k not in _COMPOSE_VARIABLES}
    full_env.update(env or {})
    with tempfile.TemporaryDirectory() as tmp:
        empty_env_file = Path(tmp) / "empty.env"
        empty_env_file.write_text("", encoding="utf-8")
        result = subprocess.run(
            [docker, "compose", "--env-file", str(empty_env_file), "config", "--format", "json"],
            cwd=ROOT,
            env=full_env,
            capture_output=True,
            text=True,
            check=False,
        )
    assert result.returncode == 0, result.stdout + result.stderr
    return cast("dict[str, Any]", json.loads(result.stdout))


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


def test_compose_config_is_valid() -> None:
    services = _compose_config()["services"]
    assert {"db", "api"} <= services.keys()


def test_compose_db_has_healthcheck() -> None:
    db = _compose_config()["services"]["db"]
    assert "pg_isready" in " ".join(db["healthcheck"]["test"])


def test_compose_api_waits_for_healthy_db() -> None:
    api = _compose_config()["services"]["api"]
    assert api["depends_on"]["db"]["condition"] == "service_healthy"


def test_compose_db_default_host_port_is_55433() -> None:
    db = _compose_config()["services"]["db"]
    assert db["ports"][0]["published"] == "55433"


def test_compose_ports_bind_loopback_only() -> None:
    services = _compose_config()["services"]
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
