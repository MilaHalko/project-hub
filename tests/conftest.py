import os
from collections.abc import AsyncIterator, Callable, Iterator
from contextlib import ExitStack
from typing import Any
from uuid import uuid4

import argon2
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from mypy_boto3_s3.client import S3Client
from pydantic import SecretStr

from project_hub.auth.passwords import PasswordHasher
from project_hub.db.database import Database
from project_hub.db.migrate import upgrade
from project_hub.db.orm import OrmDatabase
from project_hub.db.sql import SqlDatabase
from project_hub.main import create_app
from tests.isolated_settings import IsolatedSettings
from tests.support.database import (
    DEFAULT_ADMIN_URL,
    TestDatabaseConfigError,
    TestDatabaseUnavailableError,
    create_test_database,
    drop_test_database,
    truncate_tables,
)
from tests.support.mail import DEFAULT_MAILPIT_URL, DEFAULT_SMTP_PORT, mailpit_unreachable_reason
from tests.support.storage import (
    DEFAULT_S3_ENDPOINT_URL,
    TEST_S3_REGION,
    assertion_client,
    empty_bucket,
    unavailable_message,
    unreachable_reason,
)

TEST_JWT_SECRET = "test-only-secret-" + "0" * 32


@pytest.fixture(scope="session", autouse=True)
def _dummy_aws_credentials(tmp_path_factory: pytest.TempPathFactory) -> Iterator[None]:
    empty_file = tmp_path_factory.mktemp("aws") / "empty"
    empty_file.write_text("", encoding="utf-8")
    with pytest.MonkeyPatch.context() as mp:
        mp.setenv("AWS_ACCESS_KEY_ID", "test")
        mp.setenv("AWS_SECRET_ACCESS_KEY", "test")
        mp.setenv("AWS_SHARED_CREDENTIALS_FILE", str(empty_file))
        mp.setenv("AWS_CONFIG_FILE", str(empty_file))
        mp.delenv("AWS_PROFILE", raising=False)
        mp.delenv("AWS_SESSION_TOKEN", raising=False)
        yield


@pytest.fixture(autouse=True)
def _clean_env(monkeypatch: pytest.MonkeyPatch) -> None:
    for key in (
        "APP_NAME",
        "APP_DEBUG",
        "APP_DB_BACKEND",
        "APP_DATABASE_URL",
        "APP_DATABASE_URL_PARAMETER",
        "APP_JWT_SECRET",
        "APP_S3_BUCKET",
        "APP_S3_ENDPOINT_URL",
        "APP_S3_REGION",
        "APP_DOCUMENT_MAX_BYTES",
        "APP_DOCUMENT_MAX_FILES",
        "APP_PROJECT_MAX_BYTES",
        "APP_SMTP_HOST",
        "APP_SMTP_PORT",
        "APP_MAIL_FROM",
        "APP_MAIL_BACKEND",
        "APP_SES_REGION",
        "APP_PUBLIC_URL",
        "APP_WEB_URL",
    ):
        monkeypatch.delenv(key, raising=False)


@pytest.fixture
def client() -> Iterator[TestClient]:
    settings = IsolatedSettings(name="Test Hub")
    with TestClient(create_app(settings)) as c:
        yield c


@pytest.fixture(scope="session")
def database_url() -> Iterator[str]:
    admin_url = os.environ.get("TEST_DATABASE_URL", DEFAULT_ADMIN_URL)
    failure: str | None = None
    url = ""
    try:
        url = create_test_database(admin_url)
    except (TestDatabaseUnavailableError, TestDatabaseConfigError) as err:
        failure = str(err)
    if failure is not None:
        pytest.fail(failure, pytrace=False)
    try:
        yield url
    finally:
        drop_test_database(admin_url, url)


@pytest.fixture(scope="session")
def migrated_database_url(database_url: str) -> str:
    upgrade(database_url)
    return database_url


@pytest.fixture(scope="session")
def s3_endpoint_url() -> str:
    url = os.environ.get("TEST_S3_ENDPOINT_URL", DEFAULT_S3_ENDPOINT_URL)
    reason = unreachable_reason(url)
    if reason is not None:
        pytest.fail(unavailable_message(url, reason), pytrace=False)
    return url


@pytest.fixture(scope="session")
def smtp_port() -> int:
    return int(os.environ.get("TEST_SMTP_PORT", DEFAULT_SMTP_PORT))


@pytest.fixture(scope="session")
def mailpit_url() -> str:
    url = os.environ.get("TEST_MAILPIT_URL", DEFAULT_MAILPIT_URL)
    reason = mailpit_unreachable_reason(url)
    if reason is not None:
        pytest.fail(
            f"Mailpit is not reachable at {url}. "
            "Start it with: docker compose up -d --wait mail (or set TEST_MAILPIT_URL)\n"
            f"Reason: {reason}",
            pytrace=False,
        )
    return url


@pytest.fixture(scope="session")
def s3_client(s3_endpoint_url: str) -> S3Client:
    return assertion_client(s3_endpoint_url)


@pytest.fixture(scope="session")
def storage_bucket(s3_client: S3Client) -> Iterator[str]:
    bucket = f"project-hub-test-{uuid4().hex}"
    s3_client.create_bucket(
        Bucket=bucket, CreateBucketConfiguration={"LocationConstraint": TEST_S3_REGION}
    )
    try:
        yield bucket
    finally:
        empty_bucket(s3_client, bucket)
        s3_client.delete_bucket(Bucket=bucket)


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


def _build_database(backend: str, url: str) -> Database:
    """Build the `Database` for one backend name; add new backends here."""
    if backend == "orm":
        return OrmDatabase(url)
    if backend == "sql":
        return SqlDatabase(url)
    raise ValueError(f"unknown database backend: {backend!r}")


@pytest.fixture(params=["orm", "sql"], ids=["orm", "sql"])
async def database(
    request: pytest.FixtureRequest, migrated_database_url: str
) -> AsyncIterator[Database]:
    db = _build_database(request.param, migrated_database_url)
    await db.open()
    try:
        yield db
    finally:
        try:
            await db.close()
        finally:
            truncate_tables(migrated_database_url)


def _test_app(settings: IsolatedSettings) -> FastAPI:
    app = create_app(settings)
    # Cheapest Argon2 parameters keep the tests fast; never use them outside tests.
    app.state.password_hasher = PasswordHasher(
        argon2.PasswordHasher.from_parameters(argon2.profiles.CHEAPEST)
    )
    return app


@pytest.fixture(params=["orm", "sql"], ids=["orm", "sql"])
def api_client(
    request: pytest.FixtureRequest,
    migrated_database_url: str,
    s3_endpoint_url: str,
    s3_client: S3Client,
    storage_bucket: str,
    smtp_port: int,
) -> Iterator[TestClient]:
    settings = IsolatedSettings(
        db_backend=request.param,
        database_url=SecretStr(migrated_database_url),
        jwt_secret=SecretStr(TEST_JWT_SECRET),
        s3_bucket=storage_bucket,
        s3_endpoint_url=s3_endpoint_url,
        s3_region=TEST_S3_REGION,
        smtp_host="localhost",
        smtp_port=smtp_port,
        public_url="http://testserver",
    )
    try:
        with TestClient(_test_app(settings)) as c:
            yield c
    finally:
        try:
            truncate_tables(migrated_database_url)
        finally:
            empty_bucket(s3_client, storage_bucket)


@pytest.fixture
def make_api_client(api_client: TestClient) -> Iterator[Callable[..., TestClient]]:
    app = api_client.app
    assert isinstance(app, FastAPI)
    base: IsolatedSettings = app.state.settings
    with ExitStack() as stack:

        def make(**overrides: Any) -> TestClient:
            settings = IsolatedSettings(**{**base.model_dump(), **overrides})
            return stack.enter_context(TestClient(_test_app(settings)))

        yield make
