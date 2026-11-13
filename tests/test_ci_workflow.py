"""Pin the decisions of the CI workflow (``.github/workflows/ci.yml``)."""

import re
from pathlib import Path
from typing import Any, cast
from urllib.parse import urlsplit

import pytest
import yaml

from tests.support.docker import ROOT, compose_config

WORKFLOW_PATH = ROOT / ".github" / "workflows" / "ci.yml"
SHA_PINNED = re.compile(r"^[\w.-]+/[\w.-]+@[0-9a-f]{40}$")

Job = dict[str, Any]


@pytest.fixture(scope="module")
def workflow() -> dict[str, Any]:
    return cast("dict[str, Any]", yaml.safe_load(WORKFLOW_PATH.read_text(encoding="utf-8")))


@pytest.fixture(scope="module")
def jobs(workflow: dict[str, Any]) -> dict[str, Job]:
    return cast("dict[str, Job]", workflow["jobs"])


def _steps(job: Job) -> list[dict[str, Any]]:
    return cast("list[dict[str, Any]]", job["steps"])


def _runs(job: Job) -> list[str]:
    return [cast("str", step["run"]) for step in _steps(job) if "run" in step]


def _index(runs: list[str], needle: str) -> int:
    matches = [i for i, run in enumerate(runs) if needle in run]
    assert matches, f"no run step contains {needle!r}"
    return matches[0]


def _dockerfile_poetry_version() -> str:
    text = (ROOT / "Dockerfile").read_text(encoding="utf-8")
    match = re.search(r"poetry==([\d.]+)", text)
    assert match is not None
    return match.group(1)


def test_triggers(workflow: dict[str, Any]) -> None:
    # PyYAML parses the bare key ``on`` as the boolean True.
    raw = cast("dict[object, Any]", workflow)
    triggers = cast("dict[str, Any]", raw.get("on", raw.get(True)))
    assert "pull_request" in triggers
    assert triggers["push"]["branches"] == ["main"]


def test_concurrency_and_timeouts(workflow: dict[str, Any], jobs: dict[str, Job]) -> None:
    assert workflow["concurrency"]["cancel-in-progress"] is True
    assert jobs
    for name, job in jobs.items():
        assert isinstance(job.get("timeout-minutes"), int), name


def test_token_is_read_only(workflow: dict[str, Any], jobs: dict[str, Job]) -> None:
    assert workflow["permissions"] == {"contents": "read"}
    assert all("permissions" not in job for job in jobs.values())


def test_actions_are_pinned_by_sha(jobs: dict[str, Job]) -> None:
    uses = [step["uses"] for job in jobs.values() for step in _steps(job) if "uses" in step]
    assert uses
    for ref in uses:
        assert SHA_PINNED.match(ref), ref
    for job in jobs.values():
        for step in _steps(job):
            if step.get("uses", "").startswith("actions/checkout@"):
                assert step["with"]["persist-credentials"] is False


def test_python_and_poetry_match_project(jobs: dict[str, Job]) -> None:
    assert (ROOT / ".python-version").read_text(encoding="utf-8").strip() == "3.13"
    poetry_install = f"pipx install poetry=={_dockerfile_poetry_version()}"
    assert set(jobs) >= {"checks", "docker"}
    for name in ("checks", "docker"):
        setups = [
            step
            for step in _steps(jobs[name])
            if step.get("uses", "").startswith("actions/setup-python@")
        ]
        assert [s["with"]["python-version-file"] for s in setups] == [".python-version"], name
        assert any(poetry_install in run for run in _runs(jobs[name])), name
    assert any("sys.version_info[:2] == (3, 13)" in run for run in _runs(jobs["checks"]))


def test_checks_runs_all_tools_in_order(jobs: dict[str, Job]) -> None:
    runs = _runs(jobs["checks"])
    order = [
        _index(runs, "poetry run ruff check"),
        _index(runs, "poetry run ruff format --check"),
        _index(runs, "poetry run pyright"),
        _index(runs, "poetry run pytest"),
    ]
    assert order == sorted(set(order))


def test_checks_uses_compose_postgres(jobs: dict[str, Job]) -> None:
    checks = jobs["checks"]
    service = checks["services"]["postgres"]
    assert service["image"] == compose_config()["services"]["db"]["image"]
    url = urlsplit(cast("str", checks["env"]["TEST_DATABASE_URL"]))
    assert url.hostname == "localhost"
    published = [str(port).split(":") for port in service["ports"]]
    assert url.port is not None
    assert [str(url.port), "5432"] in published


def test_checks_verifies_both_backends(workflow: dict[str, Any], jobs: dict[str, Job]) -> None:
    assert workflow["defaults"]["run"]["shell"] == "bash"
    runs = _runs(jobs["checks"])
    pytest_at = _index(runs, "poetry run pytest")
    assert "-v" in runs[pytest_at].split()
    assert "tee pytest.log" in runs[pytest_at]
    coverage_at = _index(runs, "tests.support.backend_coverage pytest.log")
    assert coverage_at > pytest_at


def test_docker_job_runs_smoke_tests_in_parallel(jobs: dict[str, Job]) -> None:
    docker = jobs["docker"]
    assert any("pytest -m docker" in run for run in _runs(docker))
    assert "needs" not in docker


def test_no_aws_or_deploy() -> None:
    text = Path(WORKFLOW_PATH).read_text(encoding="utf-8").lower()
    for banned in ("aws", "ecr", "secrets.", "deploy"):
        assert banned not in text, banned
