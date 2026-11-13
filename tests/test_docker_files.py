"""Security guards for the Docker setup; the image smoke tests are opt-in (``-m docker``)."""

import json
import os
import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import Any, cast

ROOT = Path(__file__).resolve().parents[1]

_COMPOSE_VARIABLES = (
    "APP_PORT",
    "APP_DB_PORT",
    "POSTGRES_USER",
    "POSTGRES_PASSWORD",
    "POSTGRES_DB",
    "APP_DB_BACKEND",
)


def _compose_config() -> dict[str, Any]:
    """Render ``docker compose config`` with the compose defaults.

    The compose variables are removed from the inherited environment and an empty
    ``--env-file`` replaces ``.env``, so local settings cannot change the result.
    """
    docker = shutil.which("docker")
    assert docker is not None
    env = {k: v for k, v in os.environ.items() if k not in _COMPOSE_VARIABLES}
    with tempfile.TemporaryDirectory() as tmp:
        empty_env_file = Path(tmp) / "empty.env"
        empty_env_file.write_text("", encoding="utf-8")
        result = subprocess.run(
            [docker, "compose", "--env-file", str(empty_env_file), "config", "--format", "json"],
            cwd=ROOT,
            env=env,
            capture_output=True,
            text=True,
            check=False,
        )
    assert result.returncode == 0, result.stdout + result.stderr
    return cast("dict[str, Any]", json.loads(result.stdout))


def test_dockerignore_keeps_secrets_out_of_the_image() -> None:
    lines = [
        line.strip() for line in (ROOT / ".dockerignore").read_text(encoding="utf-8").splitlines()
    ]
    assert ".env" in lines
    assert ".venv/" in lines


def test_compose_ports_bind_loopback_only() -> None:
    services = _compose_config()["services"]
    for name in ("db", "api"):
        assert services[name]["ports"][0]["host_ip"] == "127.0.0.1"
