import json
import os
import shutil
import socket
import subprocess
import sys
import time
import urllib.error
import urllib.request
from collections.abc import Mapping
from importlib.metadata import version
from pathlib import Path
from typing import Protocol

import pytest

pytestmark = pytest.mark.package

ROOT = Path(__file__).resolve().parents[1]
COMMAND_TIMEOUT = 600


class RunInstalled(Protocol):
    def __call__(
        self, *args: str, env: Mapping[str, str] | None = None
    ) -> subprocess.CompletedProcess[str]: ...


def _tail(text: str, limit: int = 4000) -> str:
    return text[-limit:]


def _run(
    *args: str, cwd: Path, env: Mapping[str, str] | None = None
) -> subprocess.CompletedProcess[str]:
    try:
        return subprocess.run(
            args,
            check=True,
            capture_output=True,
            text=True,
            cwd=cwd,
            env=env,
            timeout=COMMAND_TIMEOUT,
        )
    except subprocess.CalledProcessError as err:
        raise RuntimeError(
            f"{' '.join(args)} exited with {err.returncode}\n"
            f"--- stdout ---\n{_tail(err.stdout or '')}\n"
            f"--- stderr ---\n{_tail(err.stderr or '')}"
        ) from err


def _clean_env(extra: Mapping[str, str] | None = None) -> dict[str, str]:
    env = {key: value for key, value in os.environ.items() if not key.startswith("APP_")}
    return {**env, **(extra or {})}


def _single(directory: Path, pattern: str) -> Path:
    matches = sorted(directory.glob(pattern))
    assert len(matches) == 1, f"expected one {pattern} in {directory}, found {matches}"
    return matches[0]


def _free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


def _wait_for_health(
    url: str, process: subprocess.Popen[bytes], timeout: float = 30
) -> tuple[int, str]:
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
        if status == 200 or process.poll() is not None or time.monotonic() >= deadline:
            return status, body
        time.sleep(0.5)


@pytest.fixture(scope="session")
def dist_dir(tmp_path_factory: pytest.TempPathFactory) -> Path:
    given = os.environ.get("PACKAGE_DIST_DIR")
    if given:
        return Path(given).resolve()
    poetry = shutil.which("poetry")
    assert poetry is not None, "poetry is not on PATH"
    out = tmp_path_factory.mktemp("dist")
    _run(poetry, "build", "--no-interaction", "-o", str(out), cwd=ROOT)
    return out


@pytest.fixture(scope="session")
def wheel(dist_dir: Path) -> Path:
    return _single(dist_dir, "project_hub-*.whl")


@pytest.fixture(scope="session")
def sdist(dist_dir: Path) -> Path:
    return _single(dist_dir, "project_hub-*.tar.gz")


@pytest.fixture(scope="session")
def workdir(tmp_path_factory: pytest.TempPathFactory) -> Path:
    return tmp_path_factory.mktemp("work")


@pytest.fixture(scope="session")
def venv_python(wheel: Path, tmp_path_factory: pytest.TempPathFactory, workdir: Path) -> Path:
    venv = tmp_path_factory.mktemp("venv")
    _run(sys.executable, "-I", "-m", "venv", str(venv), cwd=workdir, env=_clean_env())
    python = venv / "bin" / "python"
    _run(
        str(python),
        "-I",
        "-m",
        "pip",
        "install",
        "--disable-pip-version-check",
        "--no-input",
        str(wheel),
        cwd=workdir,
        env=_clean_env(),
    )
    return python


@pytest.fixture(scope="session")
def run_installed(venv_python: Path, workdir: Path) -> RunInstalled:
    def run(*args: str, env: Mapping[str, str] | None = None) -> subprocess.CompletedProcess[str]:
        return _run(str(venv_python), "-I", *args, cwd=workdir, env=_clean_env(env))

    return run


def test_build_makes_wheel_and_sdist(wheel: Path, sdist: Path) -> None:
    project_version = version("project-hub")

    assert wheel.name == f"project_hub-{project_version}-py3-none-any.whl"
    assert sdist.name == f"project_hub-{project_version}.tar.gz"


def test_installed_package_comes_from_site_packages(run_installed: RunInstalled) -> None:
    result = run_installed(
        "-c",
        "import json, sysconfig, project_hub; "
        "print(json.dumps([project_hub.__file__, sysconfig.get_path('purelib')]))",
    )

    module_file, site_packages = (Path(path).resolve() for path in json.loads(result.stdout))
    assert module_file.is_relative_to(site_packages)
    assert not module_file.is_relative_to(ROOT / "src")


def test_installed_app_serves_health(venv_python: Path, workdir: Path) -> None:
    port = _free_port()
    log_path = workdir / f"uvicorn-{port}.log"
    with log_path.open("wb") as log:
        process = subprocess.Popen(
            [
                str(venv_python),
                "-I",
                "-m",
                "uvicorn",
                "project_hub.main:app",
                "--host",
                "127.0.0.1",
                "--port",
                str(port),
            ],
            cwd=workdir,
            env=_clean_env(),
            stdout=log,
            stderr=subprocess.STDOUT,
        )
        try:
            status, body = _wait_for_health(f"http://127.0.0.1:{port}/health", process)
        finally:
            process.terminate()
            try:
                process.wait(timeout=10)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait(timeout=10)

    output = _tail(log_path.read_text(encoding="utf-8", errors="replace"))
    assert status == 200, f"{body}\n--- uvicorn output ---\n{output}"
    assert json.loads(body) == {"status": "ok"}
