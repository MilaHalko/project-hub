import logging

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from project_hub.main import create_app
from project_hub.storage.dependencies import Storage
from tests.isolated_settings import IsolatedSettings


def _add_test_route(app: FastAPI) -> None:
    @app.get("/_test/storage")
    async def storage_kind(storage: Storage) -> dict[str, str]:
        return {"storage": type(storage).__name__}


def test_get_storage_gives_configured_storage() -> None:
    app = create_app(IsolatedSettings(s3_bucket="project-hub-documents"))
    _add_test_route(app)

    with TestClient(app) as client:
        response = client.get("/_test/storage")

    assert response.status_code == 200
    assert response.json() == {"storage": "S3FileStorage"}


def test_get_storage_without_bucket_returns_500(caplog: pytest.LogCaptureFixture) -> None:
    app = create_app(IsolatedSettings())
    _add_test_route(app)

    with (
        caplog.at_level(logging.ERROR, logger="project_hub.core.error_handlers"),
        TestClient(app, raise_server_exceptions=False) as client,
    ):
        response = client.get("/_test/storage")

    assert response.status_code == 500
    assert response.json() == {"detail": "Internal Server Error"}
    (record,) = [r for r in caplog.records if r.name == "project_hub.core.error_handlers"]
    assert record.exc_info is not None
    error = record.exc_info[1]
    assert isinstance(error, RuntimeError)
    assert str(error) == "File storage is not configured: set APP_S3_BUCKET"
