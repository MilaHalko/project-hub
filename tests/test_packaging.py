"""Packaging guards: the project is built and locked with Poetry."""

import shutil
import subprocess
import tomllib
from pathlib import Path
from typing import Any, cast

ROOT = Path(__file__).resolve().parents[1]


def _load_toml(name: str) -> dict[str, Any]:
    return tomllib.loads((ROOT / name).read_text(encoding="utf-8"))


def test_build_backend_is_poetry_core() -> None:
    build_system = _load_toml("pyproject.toml")["build-system"]
    requires = cast("list[str]", build_system["requires"])
    assert build_system["build-backend"] == "poetry.core.masonry.api"
    assert any(r.startswith("poetry-core") for r in requires)


def test_requires_poetry_2_2_or_newer() -> None:
    pyproject = _load_toml("pyproject.toml")
    assert pyproject["tool"]["poetry"]["requires-poetry"] == ">=2.2,<3.0"


def test_poetry_lock_replaces_uv_lock() -> None:
    assert (ROOT / "poetry.lock").is_file()
    assert not (ROOT / "uv.lock").exists()


def test_poetry_lock_matches_pyproject() -> None:
    poetry = shutil.which("poetry")
    assert poetry is not None
    result = subprocess.run(
        [poetry, "check", "--lock"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stdout + result.stderr


def test_virtualenv_is_in_project() -> None:
    config = _load_toml("poetry.toml")
    assert config["virtualenvs"]["in-project"] is True
