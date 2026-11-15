from collections.abc import Iterator

import psycopg
import pytest
from fastapi.testclient import TestClient
from mypy_boto3_s3.client import S3Client

from tests.support.auth import bearer, signed_in
from tests.support.documents import (
    app_of,
    pdf_bytes,
    replace,
    upload,
    uploaded,
    with_limits,
)
from tests.support.projects import create_project
from tests.support.storage import bucket_keys

_BOUNDARY = "limit-test-boundary"
_OVER_LIMIT = 1_100_000


def _padded_body(field: str, data: bytes) -> bytes:
    return (
        (
            f"--{_BOUNDARY}\r\n"
            f'Content-Disposition: form-data; name="{field}"; filename="a.pdf"\r\n'
            "Content-Type: application/pdf\r\n\r\n"
        ).encode()
        + data
        + (f'\r\n--{_BOUNDARY}\r\nContent-Disposition: form-data; name="padding"\r\n\r\n').encode()
        + b"x" * _OVER_LIMIT
        + f"\r\n--{_BOUNDARY}--\r\n".encode()
    )


def _chunks(body: bytes) -> Iterator[bytes]:
    yield body


def _headers(token: str | None) -> dict[str, str]:
    headers = {"Content-Type": f"multipart/form-data; boundary={_BOUNDARY}"}
    if token is not None:
        headers.update(bearer(token))
    return headers


def _count(database_url: str) -> int:
    with psycopg.connect(database_url) as conn:
        row = conn.execute("SELECT count(*) FROM documents").fetchone()
    assert row is not None
    return int(row[0])


def test_post_without_content_length_is_411(api_client: TestClient) -> None:
    _, token = signed_in(api_client)
    project = create_project(api_client, token)

    r = api_client.post(
        f"/project/{project['id']}/documents",
        headers=_headers(token),
        content=_chunks(_padded_body("files", pdf_bytes())),
    )

    assert r.status_code == 411
    assert r.json() == {"detail": "Content-Length is required"}


def test_put_without_content_length_is_411(api_client: TestClient) -> None:
    _, token = signed_in(api_client)
    project = create_project(api_client, token)
    (document,) = uploaded(api_client, token, project["id"], [("a.pdf", pdf_bytes())])

    r = api_client.put(
        f"/document/{document['id']}",
        headers=_headers(token),
        content=_chunks(_padded_body("file", pdf_bytes())),
    )

    assert r.status_code == 411
    assert r.json() == {"detail": "Content-Length is required"}


def test_post_over_limit_is_413_and_route_never_runs(
    api_client: TestClient,
    migrated_database_url: str,
    s3_client: S3Client,
    storage_bucket: str,
) -> None:
    _, token = signed_in(api_client)
    project = create_project(api_client, token)

    with with_limits(app_of(api_client), max_bytes=100, max_files=1):
        r = api_client.post(
            f"/project/{project['id']}/documents",
            headers=_headers(token),
            content=_padded_body("files", pdf_bytes()),
        )

    assert r.status_code == 413
    assert r.json() == {"detail": "Request is too large"}
    assert _count(migrated_database_url) == 0
    assert bucket_keys(s3_client, storage_bucket) == []


def test_oversized_post_without_token_is_413(api_client: TestClient) -> None:
    _, token = signed_in(api_client)
    project = create_project(api_client, token)

    with with_limits(app_of(api_client), max_bytes=100, max_files=1):
        r = api_client.post(
            f"/project/{project['id']}/documents",
            headers=_headers(None),
            content=_padded_body("files", pdf_bytes()),
        )

    assert r.status_code == 413


def test_normal_sized_post_without_token_is_401(api_client: TestClient) -> None:
    _, token = signed_in(api_client)
    project = create_project(api_client, token)

    r = upload(api_client, "", project["id"], [("a.pdf", pdf_bytes())])

    assert r.status_code == 401


def test_put_over_limit_is_413_and_document_unchanged(
    api_client: TestClient,
    migrated_database_url: str,
    s3_client: S3Client,
    storage_bucket: str,
) -> None:
    _, token = signed_in(api_client)
    project = create_project(api_client, token)
    original = pdf_bytes("original")
    (document,) = uploaded(api_client, token, project["id"], [("a.pdf", original)])
    keys_before = bucket_keys(s3_client, storage_bucket)

    with with_limits(app_of(api_client), max_bytes=100):
        r = api_client.put(
            f"/document/{document['id']}",
            headers=_headers(token),
            content=_padded_body("file", pdf_bytes()),
        )

    assert r.status_code == 413
    assert r.json() == {"detail": "Request is too large"}
    assert bucket_keys(s3_client, storage_bucket) == keys_before
    download = api_client.get(f"/document/{document['id']}", headers=bearer(token))
    assert download.content == original
    assert _count(migrated_database_url) == 1


def test_other_routes_unaffected(api_client: TestClient) -> None:
    _, token = signed_in(api_client)
    project = create_project(api_client, token)
    (document,) = uploaded(api_client, token, project["id"], [("a.pdf", pdf_bytes())])

    created = api_client.post(
        "/projects",
        headers={**bearer(token), "Content-Type": "application/json"},
        content=_chunks(b'{"name": "Chunked", "description": ""}'),
    )
    downloaded = api_client.get(f"/document/{document['id']}", headers=bearer(token))

    assert created.status_code == 201, created.text
    assert downloaded.status_code == 200


def test_normal_upload_still_works(api_client: TestClient) -> None:
    _, token = signed_in(api_client)
    project = create_project(api_client, token)
    (document,) = uploaded(api_client, token, project["id"], [("a.pdf", pdf_bytes())])

    r = replace(api_client, token, document["id"], [("b.pdf", pdf_bytes("b"))])

    assert r.status_code == 200


def test_invalid_content_length_is_400(api_client: TestClient) -> None:
    _, token = signed_in(api_client)
    project = create_project(api_client, token)

    r = api_client.post(
        f"/project/{project['id']}/documents",
        headers={**_headers(token), "Content-Length": "abc"},
        content=b"",
    )

    assert r.status_code == 400
    assert r.json() == {"detail": "Invalid Content-Length"}


def test_transfer_encoding_with_small_content_length_is_411(api_client: TestClient) -> None:
    _, token = signed_in(api_client)
    project = create_project(api_client, token)

    r = api_client.post(
        f"/project/{project['id']}/documents",
        headers={**_headers(token), "Transfer-Encoding": "chunked", "Content-Length": "10"},
        content=b"",
    )

    assert r.status_code == 411
    assert r.json() == {"detail": "Content-Length is required"}


def test_duplicate_content_length_is_400(api_client: TestClient) -> None:
    _, token = signed_in(api_client)
    project = create_project(api_client, token)

    r = api_client.post(
        f"/project/{project['id']}/documents",
        headers=[
            *_headers(token).items(),
            ("Content-Length", "10"),
            ("Content-Length", "10"),
        ],
        content=b"",
    )

    assert r.status_code == 400
    assert r.json() == {"detail": "Invalid Content-Length"}


@pytest.mark.parametrize("value", ["-5", "+5", "1_000", " 5"])
def test_content_length_must_be_ascii_digits(api_client: TestClient, value: str) -> None:
    _, token = signed_in(api_client)
    project = create_project(api_client, token)

    r = api_client.post(
        f"/project/{project['id']}/documents",
        headers={**_headers(token), "Content-Length": value},
        content=b"",
    )

    assert r.status_code == 400
    assert r.json() == {"detail": "Invalid Content-Length"}


def test_trailing_slash_path_is_guarded(api_client: TestClient) -> None:
    _, token = signed_in(api_client)
    project = create_project(api_client, token)

    with with_limits(app_of(api_client), max_bytes=100, max_files=1):
        r = api_client.post(
            f"/project/{project['id']}/documents/",
            headers=_headers(token),
            content=_padded_body("files", pdf_bytes()),
        )

    assert r.status_code == 413
