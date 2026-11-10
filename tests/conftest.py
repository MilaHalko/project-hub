from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient

from project_hub.core.config import Settings
from project_hub.main import create_app


@pytest.fixture
def client() -> Iterator[TestClient]:
    settings = Settings(_env_file=None, name="Test Hub")  # pyright: ignore[reportCallIssue]
    with TestClient(create_app(settings)) as c:
        yield c
