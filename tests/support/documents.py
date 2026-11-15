import io
import zipfile
from collections.abc import Generator
from contextlib import contextmanager
from typing import Any
from uuid import uuid4

import httpx2
from fastapi import FastAPI
from fastapi.testclient import TestClient

from project_hub.core.config import Settings
from project_hub.storage.s3 import S3FileStorage, create_s3_client
from tests.support.auth import bearer

_BOUNDARY = "project-hub-test-boundary"


def pdf_bytes(marker: str = "x") -> bytes:
    return f"%PDF-1.4\n% {marker}\n%%EOF\n".encode()


def docx_bytes(marker: str = "x") -> bytes:
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        archive.writestr("[Content_Types].xml", "<Types/>")
        archive.writestr("word/document.xml", f"<document>{marker}</document>")
    return buffer.getvalue()


def zip_bytes(**members: str) -> bytes:
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        for name, content in members.items():
            archive.writestr(name, content)
    return buffer.getvalue()


PNG_BYTES = b"\x89PNG\r\n\x1a\n" + b"\x00" * 16


def _multipart(files: list[tuple[str, bytes]], field: str) -> bytes:
    body = b""
    for name, data in files:
        quoted = name.replace("\\", "\\\\").replace('"', '\\"')
        body += (
            f"--{_BOUNDARY}\r\n"
            f'Content-Disposition: form-data; name="{field}"; filename="{quoted}"\r\n'
            "Content-Type: application/octet-stream\r\n\r\n"
        ).encode()
        body += data + b"\r\n"
    return body + f"--{_BOUNDARY}--\r\n".encode()


def upload(
    client: TestClient,
    token: str,
    project_id: str,
    files: list[tuple[str, bytes]],
    field: str = "files",
) -> httpx2.Response:
    # Built by hand: httpx percent-encodes quotes and control characters in file names.
    return client.post(
        f"/project/{project_id}/documents",
        headers={
            **bearer(token),
            "Content-Type": f"multipart/form-data; boundary={_BOUNDARY}",
        },
        content=_multipart(files, field),
    )


def uploaded(
    client: TestClient, token: str, project_id: str, files: list[tuple[str, bytes]]
) -> list[dict[str, Any]]:
    r = upload(client, token, project_id, files)
    assert r.status_code == 201, r.text
    body: list[dict[str, Any]] = r.json()
    return body


def app_of(client: TestClient) -> FastAPI:
    app = client.app
    assert isinstance(app, FastAPI)
    return app


@contextmanager
def broken_storage(app: FastAPI) -> Generator[None]:
    original = app.state.storage
    app.state.storage = S3FileStorage(
        create_s3_client(app.state.settings), f"project-hub-missing-{uuid4().hex}"
    )
    try:
        yield
    finally:
        app.state.storage = original


@contextmanager
def with_limits(
    app: FastAPI, *, max_bytes: int | None = None, max_files: int | None = None
) -> Generator[None]:
    original: Settings = app.state.settings
    update: dict[str, int] = {}
    if max_bytes is not None:
        update["document_max_bytes"] = max_bytes
    if max_files is not None:
        update["document_max_files"] = max_files
    app.state.settings = original.model_copy(update=update)
    try:
        yield
    finally:
        app.state.settings = original
