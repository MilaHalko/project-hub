"""Helpers for the Docker tests."""

import json
import os
import shutil
import subprocess
import tempfile
import warnings
from pathlib import Path
from typing import Any, Final, cast

ROOT = Path(__file__).resolve().parents[2]
CLEANUP_TIMEOUT: Final = 120

_COMPOSE_VARIABLES = (
    "APP_PORT",
    "APP_DB_PORT",
    "POSTGRES_USER",
    "POSTGRES_PASSWORD",
    "POSTGRES_DB",
    "APP_DB_BACKEND",
)


def compose_config(env: dict[str, str] | None = None) -> dict[str, Any]:
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


def parse_compose_ps(stdout: str) -> list[dict[str, Any]]:
    """Parse ``docker compose ps --format json`` (one JSON array, or one object per line)."""
    text = stdout.strip()
    if not text:
        return []
    if text.startswith("["):
        return cast("list[dict[str, Any]]", json.loads(text))
    return [cast("dict[str, Any]", json.loads(line)) for line in text.splitlines() if line.strip()]


def published_port(output: str) -> int:
    """Return the host port from ``docker port`` / ``docker compose port`` output."""
    for line in output.splitlines():
        if line.strip():
            return int(line.strip().rsplit(":", 1)[1])
    raise ValueError(f"No published port in output: {output!r}")


def cleanup(
    *args: str, env: dict[str, str] | None = None, timeout: float = CLEANUP_TIMEOUT
) -> None:
    """Run a teardown command; a failure or hang must not mask the test's real failure."""
    try:
        subprocess.run(
            args,
            check=False,
            capture_output=True,
            text=True,
            cwd=ROOT,
            env=env,
            timeout=timeout,
        )
    except subprocess.TimeoutExpired:
        warnings.warn(f"Cleanup timed out after {timeout}s: {' '.join(args)}", stacklevel=2)
