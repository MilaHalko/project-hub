"""Opt-in smoke tests that build and run the real Docker image (``pytest -m docker``)."""

import json
import os
import shutil
import subprocess
import tempfile
import time
import urllib.error
import urllib.request
import uuid
from pathlib import Path

import pytest

from tests.support.docker import ROOT, cleanup, parse_compose_ps, published_port

pytestmark = pytest.mark.docker

BUILD_TIMEOUT = 900


def _docker() -> str:
    docker = shutil.which("docker")
    assert docker is not None
    return docker


def _wait_for_health(url: str, timeout: float = 60) -> tuple[int, str]:
    """Poll ``url`` until it answers 200; return the last (status, body) on timeout."""
    deadline = time.monotonic() + timeout
    status, body = 0, ""
    while True:
        try:
            with urllib.request.urlopen(url, timeout=2) as response:
                status, body = response.status, response.read().decode("utf-8")
        except urllib.error.HTTPError as error:
            status, body = error.code, error.read().decode("utf-8")
        except (urllib.error.URLError, OSError) as error:
            status, body = 0, str(error)
        if status == 200 or time.monotonic() >= deadline:
            return status, body
        time.sleep(0.5)


def _tail(text: str, limit: int = 4000) -> str:
    return text[-limit:]


def _run(*args: str, env: dict[str, str] | None = None) -> subprocess.CompletedProcess[str]:
    try:
        return subprocess.run(
            args,
            check=True,
            capture_output=True,
            text=True,
            cwd=ROOT,
            env=env,
            timeout=BUILD_TIMEOUT,
        )
    except subprocess.CalledProcessError as err:
        raise RuntimeError(
            f"{' '.join(args)} exited with {err.returncode}\n"
            f"--- stdout ---\n{_tail(err.stdout or '')}\n"
            f"--- stderr ---\n{_tail(err.stderr or '')}"
        ) from err


def _logs(*command: str, env: dict[str, str] | None = None) -> str:
    """Best-effort container logs, used only to explain a failed assertion."""
    result = subprocess.run(
        command, check=False, capture_output=True, text=True, cwd=ROOT, env=env, timeout=30
    )
    return _tail(result.stdout + result.stderr)


def test_image_serves_health_as_non_root() -> None:
    docker = _docker()
    tag = f"project-hub-smoke:{uuid.uuid4().hex}"
    container_id = ""
    try:
        _run(docker, "build", "-t", tag, ".")
        container_id = _run(docker, "run", "-d", "-p", "127.0.0.1:0:8000", tag).stdout.strip()
        port = published_port(_run(docker, "port", container_id, "8000").stdout)

        status, body = _wait_for_health(f"http://127.0.0.1:{port}/health")

        assert status == 200, f"{body}\n{_logs(docker, 'logs', container_id)}"
        assert json.loads(body) == {"status": "ok"}
        uid = _run(docker, "exec", container_id, "id", "-u").stdout.strip()
        assert uid != "0"
    finally:
        if container_id:
            cleanup(docker, "rm", "-f", container_id)
        cleanup(docker, "rmi", "-f", tag)


def test_compose_stack_serves_health() -> None:
    docker = _docker()
    project = f"project-hub-smoke-{uuid.uuid4().hex}"
    env = {**os.environ, "APP_PORT": "0", "APP_DB_PORT": "0"}
    with tempfile.TemporaryDirectory() as tmp:
        empty_env_file = Path(tmp) / "empty.env"
        empty_env_file.write_text("", encoding="utf-8")
        compose = [docker, "compose", "--env-file", str(empty_env_file), "-p", project]
        try:
            _run(*compose, "up", "-d", "--build", "--wait", env=env)
            app_port = published_port(_run(*compose, "port", "api", "8000", env=env).stdout)

            status, body = _wait_for_health(f"http://127.0.0.1:{app_port}/health")

            def compose_logs() -> str:
                return _logs(*compose, "logs", "--no-color", env=env)

            assert status == 200, f"{body}\n{compose_logs()}"
            ps = _run(*compose, "ps", "--format", "json", env=env).stdout
            running = {row["Service"]: row["State"] for row in parse_compose_ps(ps)}
            assert running == {"db": "running", "api": "running"}, compose_logs()
        finally:
            cleanup(*compose, "down", "-v", "--rmi", "local", env=env)


def test_compose_stack_migrates_database() -> None:
    docker = _docker()
    project = f"project-hub-smoke-{uuid.uuid4().hex}"
    env = {**os.environ, "APP_PORT": "0", "APP_DB_PORT": "0"}
    with tempfile.TemporaryDirectory() as tmp:
        empty_env_file = Path(tmp) / "empty.env"
        empty_env_file.write_text("", encoding="utf-8")
        compose = [docker, "compose", "--env-file", str(empty_env_file), "-p", project]
        try:
            _run(*compose, "up", "-d", "--build", "--wait", env=env)
            app_port = published_port(_run(*compose, "port", "api", "8000", env=env).stdout)

            status, body = _wait_for_health(f"http://127.0.0.1:{app_port}/health")

            def compose_logs() -> str:
                return _logs(*compose, "logs", "--no-color", env=env)

            assert status == 200, f"{body}\n{compose_logs()}"
            ps = _run(*compose, "ps", "-a", "--format", "json", env=env).stdout
            rows = {row["Service"]: row for row in parse_compose_ps(ps)}
            assert rows["migrate"]["State"] == "exited", compose_logs()
            assert rows["migrate"]["ExitCode"] == 0, compose_logs()
            table = _run(
                *compose,
                "exec",
                "-T",
                "db",
                "psql",
                "-U",
                "project_hub",
                "-d",
                "project_hub",
                "-tAc",
                "select to_regclass('public.users')",
                env=env,
            ).stdout.strip()
            assert table == "users", compose_logs()
        finally:
            cleanup(*compose, "down", "-v", "--rmi", "local", env=env)
