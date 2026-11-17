import psycopg
from fastapi.testclient import TestClient
from mypy_boto3_s3.client import S3Client

from tests.support.auth import bearer, signed_in
from tests.support.documents import app_of, pdf_bytes, replace, upload, uploaded
from tests.support.projects import create_project, used_space
from tests.support.storage import bucket_keys


def _set_limit(client: TestClient, limit: int) -> None:
    app = app_of(client)
    app.state.settings = app.state.settings.model_copy(update={"project_max_bytes": limit})


def _count(database_url: str) -> int:
    with psycopg.connect(database_url) as conn:
        row = conn.execute("SELECT count(*) FROM documents").fetchone()
    assert row is not None
    return int(row[0])


def test_upload_up_to_the_limit_is_accepted(api_client: TestClient) -> None:
    _, token = signed_in(api_client)
    project = create_project(api_client, token)
    data = pdf_bytes("fits")
    _set_limit(api_client, len(data))

    r = upload(api_client, token, project["id"], [("a.pdf", data)])

    assert r.status_code == 201, r.text
    assert used_space(api_client, token, project["id"]) == (len(data), len(data))


def test_upload_over_limit_is_refused(api_client: TestClient) -> None:
    _, token = signed_in(api_client)
    project = create_project(api_client, token)
    data = pdf_bytes("big")
    _set_limit(api_client, len(data) - 1)

    r = upload(api_client, token, project["id"], [("a.pdf", data)])

    assert r.status_code == 413
    assert r.json()["detail"].startswith("Project storage limit reached")
    assert used_space(api_client, token, project["id"]) == (0, 0)


def test_upload_over_limit_message_names_sizes(api_client: TestClient) -> None:
    _, token = signed_in(api_client)
    project = create_project(api_client, token)
    first = pdf_bytes("one")
    second = pdf_bytes("two")
    _set_limit(api_client, len(first) + 5)
    uploaded(api_client, token, project["id"], [("a.pdf", first)])

    r = upload(api_client, token, project["id"], [("b.pdf", second)])

    assert r.status_code == 413
    assert r.json() == {
        "detail": (
            f"Project storage limit reached: {len(first)} bytes of {len(first) + 5} bytes used, "
            f"this upload needs {len(second)} bytes"
        )
    }


def test_upload_over_limit_stores_nothing(
    api_client: TestClient,
    migrated_database_url: str,
    s3_client: S3Client,
    storage_bucket: str,
) -> None:
    _, token = signed_in(api_client)
    project = create_project(api_client, token)
    files = [(f"{n}.pdf", pdf_bytes(f"file-{n}")) for n in range(3)]
    each = len(files[0][1])
    _set_limit(api_client, each * 3 - 1)
    keys_before = bucket_keys(s3_client, storage_bucket)

    r = upload(api_client, token, project["id"], files)

    assert r.status_code == 413
    assert _count(migrated_database_url) == 0
    assert bucket_keys(s3_client, storage_bucket) == keys_before


def test_replace_over_limit_is_refused(api_client: TestClient) -> None:
    _, token = signed_in(api_client)
    project = create_project(api_client, token)
    old = pdf_bytes("old")
    (document,) = uploaded(api_client, token, project["id"], [("a.pdf", old)])
    bigger = pdf_bytes("old" + "x" * 50)
    _set_limit(api_client, len(old) + 10)

    r = replace(api_client, token, document["id"], [("a.pdf", bigger)])

    assert r.status_code == 413
    assert r.json()["detail"].startswith("Project storage limit reached")
    download = api_client.get(f"/document/{document['id']}", headers=bearer(token))
    assert download.status_code == 200
    assert download.content == old
    assert used_space(api_client, token, project["id"]) == (len(old), len(old))


def test_replace_over_limit_stores_nothing(
    api_client: TestClient, s3_client: S3Client, storage_bucket: str
) -> None:
    _, token = signed_in(api_client)
    project = create_project(api_client, token)
    old = pdf_bytes("old")
    (document,) = uploaded(api_client, token, project["id"], [("a.pdf", old)])
    _set_limit(api_client, len(old))
    keys_before = bucket_keys(s3_client, storage_bucket)

    r = replace(api_client, token, document["id"], [("a.pdf", pdf_bytes("old" + "x" * 50))])

    assert r.status_code == 413
    assert bucket_keys(s3_client, storage_bucket) == keys_before


def test_replace_up_to_the_limit_is_accepted(api_client: TestClient) -> None:
    _, token = signed_in(api_client)
    project = create_project(api_client, token)
    (document,) = uploaded(api_client, token, project["id"], [("a.pdf", pdf_bytes("old"))])
    new = pdf_bytes("new" + "x" * 20)
    _set_limit(api_client, len(new))

    r = replace(api_client, token, document["id"], [("a.pdf", new)])

    assert r.status_code == 200, r.text
    assert used_space(api_client, token, project["id"]) == (len(new), len(new))


def test_replace_that_shrinks_is_allowed_over_the_limit(api_client: TestClient) -> None:
    _, token = signed_in(api_client)
    project = create_project(api_client, token)
    big = pdf_bytes("big" + "x" * 100)
    (document,) = uploaded(api_client, token, project["id"], [("a.pdf", big)])
    small = pdf_bytes("small")
    _set_limit(api_client, len(small) - 1)

    r = replace(api_client, token, document["id"], [("a.pdf", small)])

    assert r.status_code == 200, r.text
    assert used_space(api_client, token, project["id"]) == (len(small), len(small))


def test_delete_is_allowed_over_the_limit(api_client: TestClient) -> None:
    _, token = signed_in(api_client)
    project = create_project(api_client, token)
    (document,) = uploaded(api_client, token, project["id"], [("a.pdf", pdf_bytes("old"))])
    _set_limit(api_client, 1)

    r = api_client.delete(f"/document/{document['id']}", headers=bearer(token))

    assert r.status_code == 204
    assert used_space(api_client, token, project["id"]) == (0, 0)
