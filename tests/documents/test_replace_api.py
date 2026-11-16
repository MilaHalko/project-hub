from datetime import datetime

import psycopg
import pytest
from fastapi.testclient import TestClient
from mypy_boto3_s3.client import S3Client

from project_hub.documents.entities import DOCX_CONTENT_TYPE, PDF_CONTENT_TYPE
from tests.support.auth import bearer, signed_in
from tests.support.documents import (
    JPEG_BYTES,
    PNG_BYTES,
    app_of,
    broken_storage,
    docx_bytes,
    pdf_bytes,
    replace,
    uploaded,
    with_limits,
    zip_bytes,
)
from tests.support.projects import add_participant, create_project, used_space
from tests.support.storage import bucket_keys


def _storage_keys(database_url: str) -> list[str]:
    with psycopg.connect(database_url) as conn:
        rows = conn.execute("SELECT storage_key FROM documents").fetchall()
    return [str(row[0]) for row in rows]


def _download(client: TestClient, token: str, document_id: str) -> bytes:
    r = client.get(f"/document/{document_id}", headers=bearer(token))
    assert r.status_code == 200, r.text
    return r.content


def test_owner_and_participant_replace(
    api_client: TestClient,
    migrated_database_url: str,
    s3_client: S3Client,
    storage_bucket: str,
) -> None:
    owner_id, owner = signed_in(api_client)
    participant_id, participant = signed_in(api_client, "anna")
    project = create_project(api_client, owner)
    add_participant(migrated_database_url, project["id"], participant_id)
    (document,) = uploaded(api_client, owner, project["id"], [("old.pdf", pdf_bytes("old"))])
    old_key = _storage_keys(migrated_database_url)[0]

    for token, user_id, login in ((participant, participant_id, "anna"), (owner, owner_id, "mila")):
        data = pdf_bytes(f"by-{login}")
        r = replace(api_client, token, document["id"], [(f"{login}.pdf", data)])

        assert r.status_code == 200, r.text
        body = r.json()
        assert body["id"] == document["id"]
        assert body["created_at"] == document["created_at"]
        assert body["name"] == f"{login}.pdf"
        assert body["size"] == len(data)
        assert body["content_type"] == PDF_CONTENT_TYPE
        assert body["uploaded_by"] == {"id": user_id, "login": login}
        assert datetime.fromisoformat(body["updated_at"]) > datetime.fromisoformat(
            document["updated_at"]
        )
        assert _download(api_client, owner, document["id"]) == data
        keys = _storage_keys(migrated_database_url)
        assert len(keys) == 1 and keys != [old_key]
        assert bucket_keys(s3_client, storage_bucket) == keys


@pytest.mark.parametrize(
    ("first", "second", "content_type"),
    [
        pytest.param(
            ("a.pdf", pdf_bytes()), ("b.docx", docx_bytes()), DOCX_CONTENT_TYPE, id="pdf-to-docx"
        ),
        pytest.param(
            ("a.docx", docx_bytes()), ("b.pdf", pdf_bytes()), PDF_CONTENT_TYPE, id="docx-to-pdf"
        ),
    ],
)
def test_pdf_and_docx_swap(
    api_client: TestClient,
    first: tuple[str, bytes],
    second: tuple[str, bytes],
    content_type: str,
) -> None:
    _, token = signed_in(api_client)
    project = create_project(api_client, token)
    (document,) = uploaded(api_client, token, project["id"], [first])

    r = replace(api_client, token, document["id"], [second])

    assert r.status_code == 200, r.text
    assert r.json()["content_type"] == content_type
    download = api_client.get(f"/document/{document['id']}", headers=bearer(token))
    assert download.headers["content-type"] == content_type
    assert download.content == second[1]


def test_outsider_and_unknown_get_404_and_nothing_changes(
    api_client: TestClient,
    migrated_database_url: str,
    s3_client: S3Client,
    storage_bucket: str,
) -> None:
    _, owner = signed_in(api_client)
    _, stranger = signed_in(api_client, "stranger")
    project = create_project(api_client, owner)
    data = pdf_bytes("old")
    (document,) = uploaded(api_client, owner, project["id"], [("old.pdf", data)])
    keys = _storage_keys(migrated_database_url)
    unknown = "00000000-0000-4000-8000-000000000000"

    outsider = replace(api_client, stranger, document["id"], [("new.pdf", pdf_bytes("new"))])
    missing = replace(api_client, owner, unknown, [("new.pdf", pdf_bytes("new"))])

    assert outsider.status_code == 404
    assert missing.status_code == 404
    assert outsider.json() == missing.json() == {"detail": "Document not found"}
    assert _download(api_client, owner, document["id"]) == data
    assert _storage_keys(migrated_database_url) == keys
    assert bucket_keys(s3_client, storage_bucket) == keys


@pytest.mark.parametrize(
    ("bad", "status"),
    [
        pytest.param(("a.pdf", b""), 422, id="empty"),
        pytest.param(("a.exe", pdf_bytes()), 422, id="wrong-extension"),
        pytest.param(("a.pdf", PNG_BYTES), 422, id="png-as-pdf"),
        pytest.param(("a.docx", pdf_bytes()), 422, id="pdf-as-docx"),
        pytest.param(("a.pdf", docx_bytes()), 422, id="docx-as-pdf"),
        pytest.param(("a.docx", zip_bytes(**{"x.txt": "y"})), 422, id="plain-zip"),
        pytest.param(("bell\x07.pdf", pdf_bytes()), 422, id="control-char"),
        pytest.param(("big.pdf", pdf_bytes().ljust(101, b"\0")), 413, id="over-limit"),
    ],
)
def test_invalid_file_keeps_old_document(
    api_client: TestClient,
    migrated_database_url: str,
    s3_client: S3Client,
    storage_bucket: str,
    bad: tuple[str, bytes],
    status: int,
) -> None:
    _, token = signed_in(api_client)
    project = create_project(api_client, token)
    data = pdf_bytes("old")
    (document,) = uploaded(api_client, token, project["id"], [("old.pdf", data)])
    keys = _storage_keys(migrated_database_url)

    with with_limits(app_of(api_client), max_bytes=100 if status == 413 else 1_000_000):
        r = replace(api_client, token, document["id"], [bad])

    assert r.status_code == status, r.text
    assert _download(api_client, token, document["id"]) == data
    assert _storage_keys(migrated_database_url) == keys
    assert bucket_keys(s3_client, storage_bucket) == keys


@pytest.mark.parametrize(
    "files",
    [
        pytest.param([], id="zero"),
        pytest.param([("a.pdf", pdf_bytes()), ("b.pdf", pdf_bytes())], id="two"),
    ],
)
def test_zero_or_two_files_is_422(
    api_client: TestClient,
    migrated_database_url: str,
    s3_client: S3Client,
    storage_bucket: str,
    files: list[tuple[str, bytes]],
) -> None:
    _, token = signed_in(api_client)
    project = create_project(api_client, token)
    (document,) = uploaded(api_client, token, project["id"], [("old.pdf", pdf_bytes())])
    keys = _storage_keys(migrated_database_url)

    r = replace(api_client, token, document["id"], files)

    assert r.status_code == 422
    assert r.json() == {"detail": "Exactly one file is required"}
    assert bucket_keys(s3_client, storage_bucket) == keys


def test_storage_unavailable_keeps_document(
    api_client: TestClient,
    migrated_database_url: str,
    s3_client: S3Client,
    storage_bucket: str,
) -> None:
    _, token = signed_in(api_client)
    project = create_project(api_client, token)
    data = pdf_bytes("old")
    (document,) = uploaded(api_client, token, project["id"], [("old.pdf", data)])
    keys = _storage_keys(migrated_database_url)

    with broken_storage(app_of(api_client)):
        r = replace(api_client, token, document["id"], [("new.pdf", pdf_bytes("new"))])

    assert r.status_code == 503
    assert r.json() == {"detail": "File storage is unavailable"}
    assert _download(api_client, token, document["id"]) == data
    assert _storage_keys(migrated_database_url) == keys
    assert bucket_keys(s3_client, storage_bucket) == keys


def test_replace_moves_project_to_top(api_client: TestClient) -> None:
    _, token = signed_in(api_client)
    older = create_project(api_client, token, "Older")
    (document,) = uploaded(api_client, token, older["id"], [("a.pdf", pdf_bytes())])
    newer = create_project(api_client, token, "Newer")
    before = api_client.get("/projects", headers=bearer(token)).json()
    assert [item["id"] for item in before] == [newer["id"], older["id"]]

    r = replace(api_client, token, document["id"], [("b.pdf", pdf_bytes("b"))])

    assert r.status_code == 200, r.text
    listed = api_client.get("/projects", headers=bearer(token)).json()
    assert [item["id"] for item in listed] == [older["id"], newer["id"]]


def test_replace_updates_project_used_space(api_client: TestClient) -> None:
    _, token = signed_in(api_client)
    project = create_project(api_client, token)
    small, other = pdf_bytes("a"), pdf_bytes("b")
    bigger = pdf_bytes("c" * 100)
    first, _ = uploaded(api_client, token, project["id"], [("a.pdf", small), ("b.pdf", other)])

    r = replace(api_client, token, first["id"], [("a.pdf", bigger)])

    assert r.status_code == 200, r.text
    total = len(bigger) + len(other)
    assert used_space(api_client, token, project["id"]) == (total, total)


@pytest.mark.parametrize(
    ("first", "second", "content_type"),
    [
        pytest.param(("a.pdf", pdf_bytes()), ("b.png", PNG_BYTES), "image/png", id="pdf-to-png"),
        pytest.param(("a.png", PNG_BYTES), ("b.jpg", JPEG_BYTES), "image/jpeg", id="png-to-jpg"),
        pytest.param(("a.jpeg", JPEG_BYTES), ("b.pdf", pdf_bytes()), PDF_CONTENT_TYPE, id="to-pdf"),
    ],
)
def test_replace_with_and_from_images(
    api_client: TestClient,
    first: tuple[str, bytes],
    second: tuple[str, bytes],
    content_type: str,
) -> None:
    _, token = signed_in(api_client)
    project = create_project(api_client, token)
    (document,) = uploaded(api_client, token, project["id"], [first])

    r = replace(api_client, token, document["id"], [second])

    assert r.status_code == 200, r.text
    assert r.json()["content_type"] == content_type
    download = api_client.get(f"/document/{document['id']}", headers=bearer(token))
    assert download.headers["content-type"] == content_type
    assert download.content == second[1]


def test_replace_with_mislabelled_image_is_422_and_keeps_old_file(
    api_client: TestClient,
) -> None:
    _, token = signed_in(api_client)
    project = create_project(api_client, token)
    data = pdf_bytes("old")
    (document,) = uploaded(api_client, token, project["id"], [("old.pdf", data)])

    r = replace(api_client, token, document["id"], [("new.png", JPEG_BYTES)])

    assert r.status_code == 422
    assert _download(api_client, token, document["id"]) == data
