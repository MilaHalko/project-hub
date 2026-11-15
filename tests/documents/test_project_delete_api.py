import logging

import psycopg
import pytest
from fastapi.testclient import TestClient
from mypy_boto3_s3.client import S3Client

from tests.support.auth import bearer, signed_in
from tests.support.documents import app_of, broken_storage, pdf_bytes, uploaded
from tests.support.projects import add_participant, create_project
from tests.support.storage import bucket_keys

STORAGE_LOGGER = "project_hub.storage.files"


def _storage_keys(database_url: str, project_id: str) -> list[str]:
    with psycopg.connect(database_url) as conn:
        rows = conn.execute(
            "SELECT storage_key FROM documents WHERE project_id = %s", (project_id,)
        ).fetchall()
    return sorted(str(row[0]) for row in rows)


def test_project_delete_removes_documents_and_files(
    api_client: TestClient,
    migrated_database_url: str,
    s3_client: S3Client,
    storage_bucket: str,
) -> None:
    _, token = signed_in(api_client)
    doomed = create_project(api_client, token, "Doomed")
    kept = create_project(api_client, token, "Kept")
    doomed_documents = uploaded(
        api_client, token, doomed["id"], [("a.pdf", pdf_bytes("a")), ("b.pdf", pdf_bytes("b"))]
    )
    (kept_document,) = uploaded(api_client, token, kept["id"], [("c.pdf", pdf_bytes("c"))])
    doomed_keys = _storage_keys(migrated_database_url, doomed["id"])
    kept_keys = _storage_keys(migrated_database_url, kept["id"])
    assert len(doomed_keys) == 2
    assert sorted(bucket_keys(s3_client, storage_bucket)) == sorted(doomed_keys + kept_keys)

    r = api_client.delete(f"/project/{doomed['id']}", headers=bearer(token))

    assert r.status_code == 204
    assert bucket_keys(s3_client, storage_bucket) == kept_keys
    assert _storage_keys(migrated_database_url, doomed["id"]) == []
    for document in doomed_documents:
        assert (
            api_client.get(f"/document/{document['id']}", headers=bearer(token)).status_code == 404
        )
    assert (
        api_client.get(f"/document/{kept_document['id']}", headers=bearer(token)).status_code == 200
    )


def test_project_delete_s3_failure_still_204_with_warning(
    api_client: TestClient,
    migrated_database_url: str,
    caplog: pytest.LogCaptureFixture,
) -> None:
    _, token = signed_in(api_client)
    project = create_project(api_client, token)
    uploaded(
        api_client, token, project["id"], [("a.pdf", pdf_bytes("a")), ("b.pdf", pdf_bytes("b"))]
    )
    keys = _storage_keys(migrated_database_url, project["id"])

    with (
        caplog.at_level(logging.WARNING, logger=STORAGE_LOGGER),
        broken_storage(app_of(api_client)),
    ):
        r = api_client.delete(f"/project/{project['id']}", headers=bearer(token))

    assert r.status_code == 204
    assert (
        api_client.get(f"/project/{project['id']}/documents", headers=bearer(token)).status_code
        == 404
    )
    assert _storage_keys(migrated_database_url, project["id"]) == []
    (record,) = [
        r
        for r in caplog.records
        if r.name == STORAGE_LOGGER
        and getattr(r, "event", None) == "document files left in storage"
    ]
    assert record.levelno == logging.WARNING
    assert sorted(vars(record)["keys"]) == keys
    assert str(vars(record)["project_id"]) == project["id"]


def test_participant_delete_touches_nothing(
    api_client: TestClient,
    migrated_database_url: str,
    s3_client: S3Client,
    storage_bucket: str,
) -> None:
    _, owner = signed_in(api_client)
    participant_id, participant = signed_in(api_client, "anna")
    project = create_project(api_client, owner)
    add_participant(migrated_database_url, project["id"], participant_id)
    (document,) = uploaded(api_client, owner, project["id"], [("a.pdf", pdf_bytes())])
    keys = _storage_keys(migrated_database_url, project["id"])

    r = api_client.delete(f"/project/{project['id']}", headers=bearer(participant))

    assert r.status_code == 403
    assert _storage_keys(migrated_database_url, project["id"]) == keys
    assert bucket_keys(s3_client, storage_bucket) == keys
    assert api_client.get(f"/document/{document['id']}", headers=bearer(owner)).status_code == 200
