from email.message import Message
from email.utils import collapse_rfc2231_value
from typing import Any
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from tests.support.auth import bearer, signed_in
from tests.support.documents import docx_bytes, pdf_bytes, uploaded
from tests.support.projects import add_participant, create_project

DOCX_TYPE = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"


def test_owner_and_participant_download_exact_bytes(
    api_client: TestClient, migrated_database_url: str, storage_bucket: str
) -> None:
    _, owner = signed_in(api_client)
    participant_id, participant = signed_in(api_client, "anna")
    project = create_project(api_client, owner)
    add_participant(migrated_database_url, project["id"], participant_id)
    data = docx_bytes("body")
    (document,) = uploaded(api_client, owner, project["id"], [("thesis.docx", data)])

    for token in (owner, participant):
        r = api_client.get(f"/document/{document['id']}", headers=bearer(token))

        assert r.status_code == 200
        assert r.content == data
        assert r.headers["content-type"] == DOCX_TYPE
        assert r.headers["content-disposition"].startswith("attachment;")
        assert r.headers["x-content-type-options"] == "nosniff"
        assert r.headers["cache-control"] == "private, no-store"


@pytest.mark.parametrize("name", ['a"b;c.pdf', "диплом.pdf"])
def test_download_header_survives_odd_names(
    api_client: TestClient, storage_bucket: str, name: str
) -> None:
    _, token = signed_in(api_client)
    project = create_project(api_client, token)
    (document,) = uploaded(api_client, token, project["id"], [(name, pdf_bytes())])

    r = api_client.get(f"/document/{document['id']}", headers=bearer(token))

    header = r.headers["content-disposition"]
    message = Message()
    message["content-disposition"] = header
    encoded = [
        value
        for key, value in message.get_params(header="content-disposition") or []
        if key == "filename" and isinstance(value, tuple)
    ]
    assert [collapse_rfc2231_value(value) for value in encoded] == [name]
    quoted = header.split("filename=", 1)[1].split(";", 1)[0]
    assert quoted.startswith('"') and quoted.endswith('"')
    assert '"' not in quoted[1:-1]
    assert "\r" not in header and "\n" not in header


def test_outsider_and_unknown_get_same_404(api_client: TestClient, storage_bucket: str) -> None:
    _, owner = signed_in(api_client)
    _, stranger = signed_in(api_client, "stranger")
    project = create_project(api_client, owner)
    (document,) = uploaded(api_client, owner, project["id"], [("a.pdf", pdf_bytes())])

    outsider = api_client.get(f"/document/{document['id']}", headers=bearer(stranger))
    unknown = api_client.get(f"/document/{uuid4()}", headers=bearer(owner))

    assert outsider.status_code == unknown.status_code == 404
    assert outsider.json() == unknown.json() == {"detail": "Document not found"}


def test_missing_object_is_503(api_client: TestClient, s3_client: Any, storage_bucket: str) -> None:
    _, token = signed_in(api_client)
    project = create_project(api_client, token)
    (document,) = uploaded(api_client, token, project["id"], [("a.pdf", pdf_bytes())])
    (key,) = [item["Key"] for item in s3_client.list_objects_v2(Bucket=storage_bucket)["Contents"]]
    s3_client.delete_object(Bucket=storage_bucket, Key=key)

    r = api_client.get(f"/document/{document['id']}", headers=bearer(token))

    assert r.status_code == 503
    assert r.json() == {"detail": "File storage is unavailable"}
