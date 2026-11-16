from datetime import datetime
from uuid import UUID, uuid4

import psycopg
import pytest
from fastapi.testclient import TestClient
from mypy_boto3_s3.client import S3Client

from project_hub.documents.entities import DOCX_CONTENT_TYPE, PDF_CONTENT_TYPE
from tests.support.auth import bearer, signed_in
from tests.support.documents import (
    PNG_BYTES,
    app_of,
    broken_storage,
    docx_bytes,
    pdf_bytes,
    upload,
    uploaded,
    with_limits,
    zip_bytes,
)
from tests.support.projects import add_participant, create_project, used_space
from tests.support.storage import bucket_keys


def _document_count(database_url: str) -> int:
    with psycopg.connect(database_url) as conn:
        row = conn.execute("SELECT count(*) FROM documents").fetchone()
    assert row is not None
    return int(row[0])


def _storage_keys(database_url: str) -> list[str]:
    with psycopg.connect(database_url) as conn:
        rows = conn.execute("SELECT storage_key FROM documents ORDER BY created_at").fetchall()
    return [str(row[0]) for row in rows]


def _object(client: S3Client, bucket: str, key: str) -> bytes:
    return client.get_object(Bucket=bucket, Key=key)["Body"].read()


def _assert_nothing_stored(database_url: str, client: S3Client, bucket: str) -> None:
    assert _document_count(database_url) == 0
    assert bucket_keys(client, bucket) == []


def test_owner_uploads_one_pdf(
    api_client: TestClient,
    migrated_database_url: str,
    s3_client: S3Client,
    storage_bucket: str,
) -> None:
    user_id, token = signed_in(api_client)
    project = create_project(api_client, token)
    data = pdf_bytes("thesis")

    r = upload(api_client, token, project["id"], [("thesis.pdf", data)])

    assert r.status_code == 201, r.text
    (document,) = r.json()
    assert set(document) == {
        "id",
        "project_id",
        "name",
        "content_type",
        "size",
        "uploaded_by",
        "created_at",
        "updated_at",
    }
    UUID(document["id"])
    assert document["project_id"] == project["id"]
    assert document["name"] == "thesis.pdf"
    assert document["content_type"] == PDF_CONTENT_TYPE
    assert document["size"] == len(data)
    assert document["uploaded_by"] == {"id": user_id, "login": "mila"}
    assert document["created_at"] == document["updated_at"]
    assert datetime.fromisoformat(document["created_at"]).tzinfo is not None
    (key,) = bucket_keys(s3_client, storage_bucket)
    assert key.startswith(f"projects/{project['id']}/documents/")
    assert _storage_keys(migrated_database_url) == [key]
    assert _object(s3_client, storage_bucket, key) == data


def test_uploads_pdf_and_docx_in_order(
    api_client: TestClient, s3_client: S3Client, storage_bucket: str
) -> None:
    _, token = signed_in(api_client)
    project = create_project(api_client, token)

    documents = uploaded(
        api_client,
        token,
        project["id"],
        [("b.pdf", pdf_bytes("b")), ("a.docx", docx_bytes("a"))],
    )

    assert [(d["name"], d["content_type"]) for d in documents] == [
        ("b.pdf", PDF_CONTENT_TYPE),
        ("a.docx", DOCX_CONTENT_TYPE),
    ]
    assert len(bucket_keys(s3_client, storage_bucket)) == 2


def test_participant_uploads(api_client: TestClient, migrated_database_url: str) -> None:
    _, mila = signed_in(api_client)
    anna_id, anna = signed_in(api_client, "anna")
    project = create_project(api_client, mila)
    add_participant(migrated_database_url, project["id"], anna_id)

    (document,) = uploaded(api_client, anna, project["id"], [("a.pdf", pdf_bytes())])

    assert document["uploaded_by"] == {"id": anna_id, "login": "anna"}
    assert document["project_id"] == project["id"]


def test_outsider_and_unknown_project_get_same_404(
    api_client: TestClient,
    migrated_database_url: str,
    s3_client: S3Client,
    storage_bucket: str,
) -> None:
    _, mila = signed_in(api_client)
    _, stranger = signed_in(api_client, "stranger")
    project = create_project(api_client, mila)

    answers = [
        upload(api_client, stranger, project["id"], [("a.pdf", pdf_bytes())]),
        upload(api_client, stranger, project["id"], [("photo.png", PNG_BYTES)]),
        upload(api_client, stranger, project["id"], []),
        upload(api_client, mila, str(uuid4()), [("a.pdf", pdf_bytes())]),
    ]

    assert [r.status_code for r in answers] == [404, 404, 404, 404]
    assert all(r.json() == {"detail": "Project not found"} for r in answers)
    _assert_nothing_stored(migrated_database_url, s3_client, storage_bucket)


@pytest.mark.parametrize(
    ("bad", "names"),
    [
        pytest.param(("photo.png", PNG_BYTES), "photo.png", id="extension"),
        pytest.param(("photo.pdf", PNG_BYTES), "photo.pdf", id="png-as-pdf"),
        pytest.param(
            ("notes.docx", zip_bytes(**{"[Content_Types].xml": "<Types/>"})),
            "notes.docx",
            id="zip-without-document",
        ),
        pytest.param(("empty.pdf", b""), "empty.pdf", id="empty"),
        pytest.param(("bell\x07.pdf", pdf_bytes()), repr("bell\x07.pdf"), id="control-char"),
    ],
)
def test_bad_file_in_batch_stores_nothing(
    api_client: TestClient,
    migrated_database_url: str,
    s3_client: S3Client,
    storage_bucket: str,
    bad: tuple[str, bytes],
    names: str,
) -> None:
    _, token = signed_in(api_client)
    project = create_project(api_client, token)

    r = upload(api_client, token, project["id"], [("good.pdf", pdf_bytes()), bad])

    assert r.status_code == 422, r.text
    assert names in r.json()["detail"]
    _assert_nothing_stored(migrated_database_url, s3_client, storage_bucket)


@pytest.mark.parametrize("name", ["+2D0-.pdf", "+2D0-.exe"])
def test_name_decoding_to_a_lone_surrogate_is_422(
    api_client: TestClient,
    migrated_database_url: str,
    s3_client: S3Client,
    storage_bucket: str,
    name: str,
) -> None:
    _, token = signed_in(api_client)
    project = create_project(api_client, token)
    boundary = "utf7-boundary"
    body = (
        (
            f"--{boundary}\r\n"
            f'Content-Disposition: form-data; name="files"; filename="{name}"\r\n'
            "Content-Type: application/pdf\r\n\r\n"
        ).encode()
        + pdf_bytes()
        + f"\r\n--{boundary}--\r\n".encode()
    )

    r = api_client.post(
        f"/project/{project['id']}/documents",
        headers={
            **bearer(token),
            "Content-Type": f"multipart/form-data; boundary={boundary}; charset=utf-7",
        },
        content=body,
    )

    assert r.status_code == 422, r.text
    assert "control characters" in r.json()["detail"]
    _assert_nothing_stored(migrated_database_url, s3_client, storage_bucket)


def test_file_over_limit_is_413(
    api_client: TestClient,
    migrated_database_url: str,
    s3_client: S3Client,
    storage_bucket: str,
) -> None:
    _, token = signed_in(api_client)
    project = create_project(api_client, token)
    data = pdf_bytes().ljust(101, b"\0")

    with with_limits(app_of(api_client), max_bytes=100):
        r = upload(api_client, token, project["id"], [("a.pdf", pdf_bytes()), ("big.pdf", data)])
        fits = upload(api_client, token, project["id"], [("full.pdf", data[:100])])

    assert r.status_code == 413
    assert r.json() == {"detail": "big.pdf: file is larger than 100 bytes"}
    assert fits.status_code == 201, fits.text
    assert _document_count(migrated_database_url) == 1
    assert len(bucket_keys(s3_client, storage_bucket)) == 1


def test_too_many_files_is_422(
    api_client: TestClient,
    migrated_database_url: str,
    s3_client: S3Client,
    storage_bucket: str,
) -> None:
    _, token = signed_in(api_client)
    project = create_project(api_client, token)
    files = [(f"{n}.pdf", pdf_bytes()) for n in range(3)]

    with with_limits(app_of(api_client), max_files=2):
        r = upload(api_client, token, project["id"], files)
        two = upload(api_client, token, project["id"], files[:2])

    assert r.status_code == 422
    assert r.json() == {"detail": "Too many files: at most 2 per request"}
    assert two.status_code == 201, two.text
    assert _document_count(migrated_database_url) == 2
    assert len(bucket_keys(s3_client, storage_bucket)) == 2


def test_no_files_is_422(
    api_client: TestClient,
    migrated_database_url: str,
    s3_client: S3Client,
    storage_bucket: str,
) -> None:
    _, token = signed_in(api_client)
    project = create_project(api_client, token)

    r = upload(api_client, token, project["id"], [])

    assert r.status_code == 422
    assert r.json() == {"detail": "No files were sent"}
    _assert_nothing_stored(migrated_database_url, s3_client, storage_bucket)


def test_wrong_field_name_is_422(
    api_client: TestClient,
    migrated_database_url: str,
    s3_client: S3Client,
    storage_bucket: str,
) -> None:
    _, token = signed_in(api_client)
    project = create_project(api_client, token)

    r = upload(api_client, token, project["id"], [("a.pdf", pdf_bytes())], field="file")

    assert r.status_code == 422
    assert r.json() == {"detail": "No files were sent"}
    _assert_nothing_stored(migrated_database_url, s3_client, storage_bucket)


def test_body_that_is_not_multipart_is_422(api_client: TestClient) -> None:
    _, token = signed_in(api_client)
    project = create_project(api_client, token)

    r = api_client.post(
        f"/project/{project['id']}/documents",
        headers={**bearer(token), "Content-Type": "multipart/form-data; boundary=x"},
        content=b"not multipart",
    )

    assert r.status_code == 422
    assert r.json()["detail"].startswith("Invalid multipart form")


@pytest.mark.parametrize("raw", ["../../etc/x.pdf", "C:\\tmp\\x.pdf"])
def test_path_in_file_name_is_dropped(
    api_client: TestClient, s3_client: S3Client, storage_bucket: str, raw: str
) -> None:
    _, token = signed_in(api_client)
    project = create_project(api_client, token)

    (document,) = uploaded(api_client, token, project["id"], [(raw, pdf_bytes())])

    assert document["name"] == "x.pdf"
    (key,) = bucket_keys(s3_client, storage_bucket)
    assert "x.pdf" not in key
    assert ".." not in key


def test_same_name_twice_allowed(api_client: TestClient) -> None:
    _, token = signed_in(api_client)
    project = create_project(api_client, token)

    (first,) = uploaded(api_client, token, project["id"], [("a.pdf", pdf_bytes("1"))])
    (second,) = uploaded(api_client, token, project["id"], [("a.pdf", pdf_bytes("2"))])

    assert first["name"] == second["name"] == "a.pdf"
    assert first["id"] != second["id"]


def test_storage_unavailable_is_503_and_no_row(
    api_client: TestClient,
    migrated_database_url: str,
    s3_client: S3Client,
    storage_bucket: str,
) -> None:
    _, token = signed_in(api_client)
    project = create_project(api_client, token)

    with broken_storage(app_of(api_client)):
        r = upload(api_client, token, project["id"], [("a.pdf", pdf_bytes())])

    assert r.status_code == 503
    assert r.json() == {"detail": "File storage is unavailable"}
    _assert_nothing_stored(migrated_database_url, s3_client, storage_bucket)


def test_upload_moves_project_to_top(api_client: TestClient) -> None:
    _, token = signed_in(api_client)
    older = create_project(api_client, token, "Older")
    newer = create_project(api_client, token, "Newer")

    uploaded(api_client, token, older["id"], [("a.pdf", pdf_bytes())])

    listed = api_client.get("/projects", headers=bearer(token)).json()
    assert [item["id"] for item in listed] == [older["id"], newer["id"]]
    assert datetime.fromisoformat(listed[0]["updated_at"]) > datetime.fromisoformat(
        older["updated_at"]
    )


def test_upper_case_extension_accepted(api_client: TestClient) -> None:
    _, token = signed_in(api_client)
    project = create_project(api_client, token)

    documents = uploaded(
        api_client,
        token,
        project["id"],
        [("THESIS.PDF", pdf_bytes()), ("Notes.DocX", docx_bytes())],
    )

    assert [(d["name"], d["content_type"]) for d in documents] == [
        ("THESIS.PDF", PDF_CONTENT_TYPE),
        ("Notes.DocX", DOCX_CONTENT_TYPE),
    ]


@pytest.mark.parametrize(
    ("name", "data", "detail"),
    [
        pytest.param(
            "a.docx", pdf_bytes(), "a.docx: content is not a valid docx", id="pdf-as-docx"
        ),
        pytest.param("a.pdf", docx_bytes(), "a.pdf: content is not a valid pdf", id="docx-as-pdf"),
    ],
)
def test_content_must_match_extension(
    api_client: TestClient,
    migrated_database_url: str,
    s3_client: S3Client,
    storage_bucket: str,
    name: str,
    data: bytes,
    detail: str,
) -> None:
    _, token = signed_in(api_client)
    project = create_project(api_client, token)

    r = upload(api_client, token, project["id"], [(name, data)])

    assert r.status_code == 422
    assert r.json() == {"detail": detail}
    _assert_nothing_stored(migrated_database_url, s3_client, storage_bucket)


def test_same_file_twice_in_one_request(
    api_client: TestClient,
    migrated_database_url: str,
    s3_client: S3Client,
    storage_bucket: str,
) -> None:
    _, token = signed_in(api_client)
    project = create_project(api_client, token)
    data = pdf_bytes("same")

    documents = uploaded(api_client, token, project["id"], [("a.pdf", data), ("a.pdf", data)])

    assert len({d["id"] for d in documents}) == 2
    keys = _storage_keys(migrated_database_url)
    assert len(set(keys)) == 2
    assert sorted(bucket_keys(s3_client, storage_bucket)) == sorted(keys)
    assert [_object(s3_client, storage_bucket, key) for key in keys] == [data, data]


def test_unicode_name_round_trips(api_client: TestClient) -> None:
    _, token = signed_in(api_client)
    project = create_project(api_client, token)

    (document,) = uploaded(api_client, token, project["id"], [("диплом.pdf", pdf_bytes())])

    assert document["name"] == "диплом.pdf"


def test_upload_adds_sizes_to_project_used_space(api_client: TestClient) -> None:
    _, token = signed_in(api_client)
    project = create_project(api_client, token)
    first, second = pdf_bytes("a"), pdf_bytes("bb")

    uploaded(api_client, token, project["id"], [("a.pdf", first), ("b.pdf", second)])

    total = len(first) + len(second)
    assert used_space(api_client, token, project["id"]) == (total, total)
