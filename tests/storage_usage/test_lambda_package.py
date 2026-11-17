import json
import shutil
import subprocess
import time
import urllib.error
import urllib.request
import zipfile
from collections.abc import Iterator
from pathlib import Path
from urllib.parse import urlsplit, urlunsplit
from uuid import UUID, uuid4

import psycopg
import pytest
from mypy_boto3_s3.client import S3Client

from tests.support.docker import ROOT, cleanup, published_port
from tests.support.storage import TEST_S3_REGION
from tests.support.storage_usage import created_event

pytestmark = pytest.mark.lambda_package

IMAGE = "public.ecr.aws/lambda/python:3.13"
HANDLER = "project_hub.storage_usage.handler.handler"
SCRIPT = ROOT / "scripts" / "build_storage_usage_lambda.sh"
COMMAND_TIMEOUT = 900
HOST_FROM_CONTAINER = "host.docker.internal"


def _tail(text: str, limit: int = 4000) -> str:
    return text[-limit:]


def _run(*args: str) -> subprocess.CompletedProcess[str]:
    result = subprocess.run(
        args, check=False, capture_output=True, text=True, cwd=ROOT, timeout=COMMAND_TIMEOUT
    )
    assert result.returncode == 0, (
        f"{' '.join(args)} exited with {result.returncode}\n"
        f"--- stdout ---\n{_tail(result.stdout)}\n--- stderr ---\n{_tail(result.stderr)}"
    )
    return result


def _for_container(url: str) -> str:
    parts = urlsplit(url)
    userinfo = parts.netloc.rpartition("@")[0]
    port = f":{parts.port}" if parts.port else ""
    netloc = f"{userinfo}@" if userinfo else ""
    return urlunsplit(parts._replace(netloc=f"{netloc}{HOST_FROM_CONTAINER}{port}"))


@pytest.fixture(scope="module")
def built_zip(tmp_path_factory: pytest.TempPathFactory) -> Path:
    out = tmp_path_factory.mktemp("lambda") / "storage-usage-lambda.zip"
    _run("bash", str(SCRIPT), str(out))
    return out


@pytest.fixture(scope="module")
def task_dir(built_zip: Path, tmp_path_factory: pytest.TempPathFactory) -> Path:
    target = tmp_path_factory.mktemp("task")
    with zipfile.ZipFile(built_zip) as archive:
        archive.extractall(target)
    return target


@pytest.fixture
def project_id(migrated_database_url: str) -> Iterator[UUID]:
    user_id, pid = uuid4(), uuid4()
    with psycopg.connect(migrated_database_url, autocommit=True) as conn:
        conn.execute(
            "INSERT INTO users (id, login, password_hash) VALUES (%s, %s, 'x')",
            (user_id, f"u-{user_id.hex}"),
        )
        conn.execute(
            "INSERT INTO projects (id, owner_id, name) VALUES (%s, %s, 'P')", (pid, user_id)
        )
    yield pid
    with psycopg.connect(migrated_database_url, autocommit=True) as conn:
        conn.execute("DELETE FROM projects WHERE id = %s", (pid,))
        conn.execute("DELETE FROM users WHERE id = %s", (user_id,))


def _invoke(port: int, event: dict[str, object], timeout: float = 30) -> tuple[int, str]:
    url = f"http://127.0.0.1:{port}/2015-03-31/functions/function/invocations"
    request = urllib.request.Request(url, data=json.dumps(event).encode(), method="POST")
    deadline = time.monotonic() + timeout
    while True:
        try:
            with urllib.request.urlopen(request, timeout=60) as response:
                return response.status, response.read().decode()
        except urllib.error.HTTPError as error:
            return error.code, error.read().decode()
        except (urllib.error.URLError, OSError):
            if time.monotonic() >= deadline:
                raise
            time.sleep(0.5)


def test_zip_holds_only_the_handler_and_its_drivers(built_zip: Path) -> None:
    with zipfile.ZipFile(built_zip) as archive:
        names = archive.namelist()

    assert "project_hub/__init__.py" in names
    assert "project_hub/storage_usage/handler.py" in names
    assert any(name.startswith("psycopg/") for name in names)
    assert any(name.startswith("psycopg_binary/") for name in names)
    assert not any(name.startswith(("boto3/", "botocore/")) for name in names)
    app_files = {name for name in names if name.startswith("project_hub/") and name[-1] != "/"}
    assert app_files == {
        "project_hub/__init__.py",
        "project_hub/storage_usage/__init__.py",
        "project_hub/storage_usage/handler.py",
    }


def test_handler_recounts_usage_inside_the_lambda_runtime(
    task_dir: Path,
    migrated_database_url: str,
    s3_endpoint_url: str,
    s3_client: S3Client,
    storage_bucket: str,
    project_id: UUID,
) -> None:
    docker = shutil.which("docker")
    assert docker is not None
    key = f"projects/{project_id}/documents/{uuid4().hex}"
    s3_client.put_object(Bucket=storage_bucket, Key=key, Body=b"x" * 123)
    name = f"lambda-smoke-{uuid4().hex[:12]}"

    try:
        _run(
            docker,
            "run",
            "--detach",
            "--name",
            name,
            "--platform",
            "linux/arm64",
            "--add-host",
            f"{HOST_FROM_CONTAINER}:host-gateway",
            "-p",
            "127.0.0.1:0:8080",
            "-v",
            f"{task_dir}:/var/task:ro",
            "-e",
            f"APP_DATABASE_URL={_for_container(migrated_database_url)}",
            "-e",
            f"APP_S3_ENDPOINT_URL={_for_container(s3_endpoint_url)}",
            "-e",
            f"APP_S3_REGION={TEST_S3_REGION}",
            "-e",
            "AWS_ACCESS_KEY_ID=test",
            "-e",
            "AWS_SECRET_ACCESS_KEY=test",
            IMAGE,
            HANDLER,
        )
        port = published_port(_run(docker, "port", name, "8080/tcp").stdout)
        status, body = _invoke(port, created_event(storage_bucket, key))
        logs = subprocess.run(
            [docker, "logs", name], check=False, capture_output=True, text=True, timeout=60
        )
    finally:
        cleanup(docker, "rm", "--force", name)

    assert status == 200, f"{body}\n{_tail(logs.stdout + logs.stderr)}"
    assert json.loads(body) == {"batchItemFailures": []}, _tail(logs.stdout + logs.stderr)
    with psycopg.connect(migrated_database_url) as conn:
        row = conn.execute(
            "SELECT storage_used_bytes FROM projects WHERE id = %s", (project_id,)
        ).fetchone()
    assert row == (123,)
