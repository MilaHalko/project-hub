"""Helpers for the Docker tests."""

import json
import subprocess
import warnings
from pathlib import Path
from typing import Any, Final, cast

ROOT = Path(__file__).resolve().parents[2]
CLEANUP_TIMEOUT: Final = 120


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
