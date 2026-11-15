import logging
from uuid import uuid4

import psycopg
import pytest
from fastapi.testclient import TestClient
from mypy_boto3_s3.client import S3Client

from tests.support.auth import bearer, signed_in
from tests.support.documents import app_of, broken_storage, pdf_bytes, uploaded
from tests.support.projects import add_participant, create_project
from tests.support.storage import bucket_keys

STORAGE_LOGGER = "project_hub.storage.files"


def _storage_keys(database_url: str) -> list[str]:
    with psycopg.connect(database_url) as conn:
        rows = conn.execute("SELECT storage_key FROM documents").fetchall()
    return [str(row[0]) for row in rows]


def test_owner_and_participant_delete(
    api_client: TestClient,
    migrated_database_url: str,
    s3_client: S3Client,
    storage_bucket: str,
) -> None:
    _, owner = signed_in(api_client)
    participant_id, participant = signed_in(api_client, "anna")
    project = create_project(api_client, owner)
    add_participant(migrated_database_url, project["id"], participant_id)
    by_owner, by_participant = uploaded(
        api_client,
        owner,
        project["id"],
        [("a.pdf", pdf_bytes("a")), ("b.pdf", pdf_bytes("b"))],
    )

    for token, document in ((owner, by_owner), (participant, by_participant)):
        r = api_client.delete(f"/document/{document['id']}", headers=bearer(token))

        assert r.status_code == 204
        assert r.content == b""
        assert (
            api_client.get(f"/document/{document['id']}", headers=bearer(owner)).status_code == 404
        )

    listed = api_client.get(f"/project/{project['id']}/documents", headers=bearer(owner))
    assert listed.json() == []
    assert _storage_keys(migrated_database_url) == []
    assert bucket_keys(s3_client, storage_bucket) == []


def test_outsider_and_unknown_get_404_nothing_deleted(
    api_client: TestClient,
    migrated_database_url: str,
    s3_client: S3Client,
    storage_bucket: str,
) -> None:
    _, owner = signed_in(api_client)
    _, stranger = signed_in(api_client, "stranger")
    project = create_project(api_client, owner)
    (document,) = uploaded(api_client, owner, project["id"], [("a.pdf", pdf_bytes())])
    keys = _storage_keys(migrated_database_url)

    outsider = api_client.delete(f"/document/{document['id']}", headers=bearer(stranger))
    unknown = api_client.delete(f"/document/{uuid4()}", headers=bearer(owner))

    for r in (outsider, unknown):
        assert r.status_code == 404
        assert r.json() == {"detail": "Document not found"}
    assert _storage_keys(migrated_database_url) == keys
    assert bucket_keys(s3_client, storage_bucket) == keys
    assert api_client.get(f"/document/{document['id']}", headers=bearer(owner)).status_code == 200


def test_s3_failure_still_204_with_warning(
    api_client: TestClient,
    migrated_database_url: str,
    caplog: pytest.LogCaptureFixture,
) -> None:
    _, token = signed_in(api_client)
    project = create_project(api_client, token)
    (document,) = uploaded(api_client, token, project["id"], [("a.pdf", pdf_bytes())])
    (key,) = _storage_keys(migrated_database_url)

    with (
        caplog.at_level(logging.WARNING, logger=STORAGE_LOGGER),
        broken_storage(app_of(api_client)),
    ):
        r = api_client.delete(f"/document/{document['id']}", headers=bearer(token))

    assert r.status_code == 204
    assert _storage_keys(migrated_database_url) == []
    (record,) = [
        r
        for r in caplog.records
        if r.name == STORAGE_LOGGER
        and getattr(r, "event", None) == "document files left in storage"
    ]
    assert record.levelno == logging.WARNING
    assert vars(record)["keys"] == [key]
    assert key in record.getMessage()


def test_delete_moves_project_to_top(api_client: TestClient) -> None:
    _, token = signed_in(api_client)
    older = create_project(api_client, token, "Older")
    (document,) = uploaded(api_client, token, older["id"], [("a.pdf", pdf_bytes())])
    newer = create_project(api_client, token, "Newer")
    before = api_client.get("/projects", headers=bearer(token)).json()
    assert [item["id"] for item in before] == [newer["id"], older["id"]]

    r = api_client.delete(f"/document/{document['id']}", headers=bearer(token))

    assert r.status_code == 204
    listed = api_client.get("/projects", headers=bearer(token)).json()
    assert [item["id"] for item in listed] == [older["id"], newer["id"]]
