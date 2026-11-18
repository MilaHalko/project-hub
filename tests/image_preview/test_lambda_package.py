import shutil
import subprocess
import zipfile
from io import BytesIO
from pathlib import Path
from uuid import uuid4

import pytest
from mypy_boto3_s3.client import S3Client
from PIL import Image

from tests.support.docker import ROOT, cleanup, published_port
from tests.support.image_preview import image_bytes, object_event
from tests.support.lambda_runtime import (
    HOST_FROM_CONTAINER,
    IMAGE,
    for_container,
    invoke,
    run,
    tail,
)
from tests.support.storage import TEST_S3_REGION

pytestmark = pytest.mark.lambda_package

HANDLER = "project_hub.image_preview.handler.handler"
SCRIPT = ROOT / "scripts" / "build_image_preview_lambda.sh"


@pytest.fixture(scope="module")
def built_zip(tmp_path_factory: pytest.TempPathFactory) -> Path:
    out = tmp_path_factory.mktemp("lambda") / "image-preview-lambda.zip"
    run("bash", str(SCRIPT), str(out))
    return out


@pytest.fixture(scope="module")
def task_dir(built_zip: Path, tmp_path_factory: pytest.TempPathFactory) -> Path:
    target = tmp_path_factory.mktemp("task")
    with zipfile.ZipFile(built_zip) as archive:
        archive.extractall(target)
    return target


def test_zip_holds_only_the_handler_and_pillow(built_zip: Path) -> None:
    with zipfile.ZipFile(built_zip) as archive:
        names = archive.namelist()

    assert any(name.startswith("PIL/") for name in names)
    assert not any(name.startswith(("boto3/", "botocore/", "psycopg")) for name in names)
    app_files = {name for name in names if name.startswith("project_hub/") and name[-1] != "/"}
    assert app_files == {
        "project_hub/__init__.py",
        "project_hub/image_preview/__init__.py",
        "project_hub/image_preview/handler.py",
    }


def test_handler_makes_and_removes_a_preview_inside_the_lambda_runtime(
    task_dir: Path, s3_endpoint_url: str, s3_client: S3Client, storage_bucket: str
) -> None:
    docker = shutil.which("docker")
    assert docker is not None
    project_id, name = uuid4(), uuid4().hex
    key = f"projects/{project_id}/documents/{name}"
    preview_key = f"projects/{project_id}/previews/{name}.jpg"
    s3_client.put_object(Bucket=storage_bucket, Key=key, Body=image_bytes((1200, 800)))
    container = f"lambda-smoke-{uuid4().hex[:12]}"

    try:
        run(
            docker,
            "run",
            "--detach",
            "--name",
            container,
            "--platform",
            "linux/arm64",
            "--add-host",
            f"{HOST_FROM_CONTAINER}:host-gateway",
            "-p",
            "127.0.0.1:0:8080",
            "-v",
            f"{task_dir}:/var/task:ro",
            "-e",
            f"APP_S3_ENDPOINT_URL={for_container(s3_endpoint_url)}",
            "-e",
            f"APP_S3_REGION={TEST_S3_REGION}",
            "-e",
            "AWS_ACCESS_KEY_ID=test",
            "-e",
            "AWS_SECRET_ACCESS_KEY=test",
            IMAGE,
            HANDLER,
        )
        port = published_port(run(docker, "port", container, "8080/tcp").stdout)
        created = invoke(port, object_event(storage_bucket, key))
        stored = s3_client.get_object(Bucket=storage_bucket, Key=preview_key)
        preview = Image.open(BytesIO(stored["Body"].read()))
        deleted = invoke(port, object_event(storage_bucket, key, "Object Deleted"))
        remaining = s3_client.list_objects_v2(Bucket=storage_bucket, Prefix=preview_key)
        logs = subprocess.run(
            [docker, "logs", container], check=False, capture_output=True, text=True, timeout=60
        )
    finally:
        cleanup(docker, "rm", "--force", container)

    context = tail(logs.stdout + logs.stderr)
    assert created[0] == 200, f"{created[1]}\n{context}"
    assert preview.format == "JPEG"
    assert max(preview.size) <= 512
    assert deleted[0] == 200, f"{deleted[1]}\n{context}"
    assert remaining.get("KeyCount", 0) == 0
