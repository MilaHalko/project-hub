from uuid import uuid4

from fastapi.testclient import TestClient
from mypy_boto3_s3.client import S3Client

from project_hub.documents.entities import preview_key
from project_hub.image_preview.handler import (
    _preview_key as lambda_preview_key,  # pyright: ignore[reportPrivateUsage]
)
from tests.support.auth import bearer, signed_in
from tests.support.documents import JPEG_BYTES, PNG_BYTES, pdf_bytes, uploaded
from tests.support.projects import add_participant, create_project
from tests.support.storage import bucket_keys

PREVIEW = b"\xff\xd8\xff preview"
NOT_READY = {"detail": "The preview is not ready yet. Try again in a few seconds."}
NO_PREVIEW = {"detail": "This document has no preview"}


def _document_key(s3_client: S3Client, bucket: str) -> str:
    (key,) = bucket_keys(s3_client, bucket)
    return key


def test_preview_key_matches_the_lambda_key() -> None:
    key = f"projects/{uuid4()}/documents/{uuid4().hex}"

    assert preview_key(key) == lambda_preview_key(key)
    assert preview_key(key).startswith(key.split("/documents/")[0] + "/previews/")
    assert preview_key(key).endswith(".jpg")


def test_owner_and_participant_get_the_preview(
    api_client: TestClient,
    migrated_database_url: str,
    storage_bucket: str,
    s3_client: S3Client,
) -> None:
    _, owner = signed_in(api_client)
    participant_id, participant = signed_in(api_client, "anna")
    project = create_project(api_client, owner)
    add_participant(migrated_database_url, project["id"], participant_id)
    (document,) = uploaded(api_client, owner, project["id"], [("a.png", PNG_BYTES)])
    key = _document_key(s3_client, storage_bucket)
    s3_client.put_object(
        Bucket=storage_bucket, Key=preview_key(key), Body=PREVIEW, ContentType="image/jpeg"
    )

    for token in (owner, participant):
        r = api_client.get(f"/document/{document['id']}/preview", headers=bearer(token))

        assert r.status_code == 200
        assert r.content == PREVIEW
        assert r.headers["content-type"] == "image/jpeg"
        assert "content-disposition" not in r.headers
        assert r.headers["x-content-type-options"] == "nosniff"
        assert r.headers["cache-control"] == "private, max-age=300"


def test_jpeg_document_gets_the_preview_too(
    api_client: TestClient, storage_bucket: str, s3_client: S3Client
) -> None:
    _, token = signed_in(api_client)
    project = create_project(api_client, token)
    (document,) = uploaded(api_client, token, project["id"], [("a.jpg", JPEG_BYTES)])
    key = _document_key(s3_client, storage_bucket)
    s3_client.put_object(Bucket=storage_bucket, Key=preview_key(key), Body=PREVIEW)

    r = api_client.get(f"/document/{document['id']}/preview", headers=bearer(token))

    assert r.status_code == 200
    assert r.content == PREVIEW


def test_preview_not_ready_before_the_lambda_wrote_it(
    api_client: TestClient, storage_bucket: str
) -> None:
    _, token = signed_in(api_client)
    project = create_project(api_client, token)
    (document,) = uploaded(api_client, token, project["id"], [("a.png", PNG_BYTES)])

    r = api_client.get(f"/document/{document['id']}/preview", headers=bearer(token))

    assert r.status_code == 404
    assert r.json() == NOT_READY


def test_pdf_has_no_preview(api_client: TestClient, storage_bucket: str) -> None:
    _, token = signed_in(api_client)
    project = create_project(api_client, token)
    (document,) = uploaded(api_client, token, project["id"], [("a.pdf", pdf_bytes())])

    r = api_client.get(f"/document/{document['id']}/preview", headers=bearer(token))

    assert r.status_code == 404
    assert r.json() == NO_PREVIEW


def test_outsider_and_unknown_get_same_404(
    api_client: TestClient, storage_bucket: str, s3_client: S3Client
) -> None:
    _, owner = signed_in(api_client)
    _, stranger = signed_in(api_client, "stranger")
    project = create_project(api_client, owner)
    (document,) = uploaded(api_client, owner, project["id"], [("a.png", PNG_BYTES)])
    key = _document_key(s3_client, storage_bucket)
    s3_client.put_object(Bucket=storage_bucket, Key=preview_key(key), Body=PREVIEW)

    outsider = api_client.get(f"/document/{document['id']}/preview", headers=bearer(stranger))
    unknown = api_client.get(f"/document/{uuid4()}/preview", headers=bearer(owner))

    assert outsider.status_code == unknown.status_code == 404
    assert outsider.json() == unknown.json() == {"detail": "Document not found"}


def test_preview_needs_a_token(api_client: TestClient, storage_bucket: str) -> None:
    r = api_client.get(f"/document/{uuid4()}/preview")

    assert r.status_code == 401


def test_deleted_document_has_no_preview(
    api_client: TestClient, storage_bucket: str, s3_client: S3Client
) -> None:
    _, token = signed_in(api_client)
    project = create_project(api_client, token)
    (document,) = uploaded(api_client, token, project["id"], [("a.png", PNG_BYTES)])
    key = _document_key(s3_client, storage_bucket)
    s3_client.put_object(Bucket=storage_bucket, Key=preview_key(key), Body=PREVIEW)
    api_client.delete(f"/document/{document['id']}", headers=bearer(token))

    r = api_client.get(f"/document/{document['id']}/preview", headers=bearer(token))

    assert r.status_code == 404
    assert r.json() == {"detail": "Document not found"}
