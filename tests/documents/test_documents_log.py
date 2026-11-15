import logging
from uuid import UUID

import pytest
from fastapi.testclient import TestClient

from tests.support.auth import bearer, signed_in
from tests.support.documents import docx_bytes, pdf_bytes, replace, upload, uploaded
from tests.support.projects import create_project

LOGGER = "project_hub.documents.service"


def _field(record: logging.LogRecord, name: str) -> object:
    return getattr(record, name)


def test_upload_logs_each_document_without_its_name(
    api_client: TestClient, caplog: pytest.LogCaptureFixture
) -> None:
    user_id, token = signed_in(api_client)
    project = create_project(api_client, token)

    with caplog.at_level(logging.INFO, logger=LOGGER):
        documents = uploaded(
            api_client,
            token,
            project["id"],
            [("secret-thesis.pdf", pdf_bytes()), ("secret-notes.docx", docx_bytes())],
        )

    records = [r for r in caplog.records if r.name == LOGGER]
    assert [r.levelno for r in records] == [logging.INFO, logging.INFO]
    assert [_field(r, "document_id") for r in records] == [UUID(d["id"]) for d in documents]
    for record in records:
        assert _field(record, "event") == "document uploaded"
        assert record.getMessage().startswith("document uploaded")
        assert _field(record, "login") == "mila"
        assert _field(record, "user_id") == UUID(user_id)
        assert _field(record, "project_id") == UUID(project["id"])
        assert "secret" not in record.getMessage()
        assert not any("secret" in str(value) for value in vars(record).values())


def test_refused_upload_is_not_logged(
    api_client: TestClient, caplog: pytest.LogCaptureFixture
) -> None:
    _, token = signed_in(api_client)
    project = create_project(api_client, token)

    with caplog.at_level(logging.INFO, logger=LOGGER):
        r = upload(api_client, token, project["id"], [("a.pdf", b"")])

    assert r.status_code == 422
    assert not [r for r in caplog.records if r.name == LOGGER]


def test_replace_logs_one_event_without_names(
    api_client: TestClient, caplog: pytest.LogCaptureFixture
) -> None:
    user_id, token = signed_in(api_client)
    project = create_project(api_client, token)
    (document,) = uploaded(api_client, token, project["id"], [("old-secret.pdf", pdf_bytes())])

    with caplog.at_level(logging.INFO, logger=LOGGER):
        r = replace(api_client, token, document["id"], [("new-secret.docx", docx_bytes())])

    assert r.status_code == 200, r.text
    (record,) = [
        r for r in caplog.records if r.name == LOGGER and _field(r, "event") == "document replaced"
    ]
    assert record.levelno == logging.INFO
    assert record.getMessage().startswith("document replaced")
    assert _field(record, "login") == "mila"
    assert _field(record, "user_id") == UUID(user_id)
    assert _field(record, "project_id") == UUID(project["id"])
    assert _field(record, "document_id") == UUID(document["id"])
    assert not any("secret" in str(value) for value in vars(record).values())


def test_delete_logs_one_event_without_name(
    api_client: TestClient, caplog: pytest.LogCaptureFixture
) -> None:
    user_id, token = signed_in(api_client)
    project = create_project(api_client, token)
    (document,) = uploaded(api_client, token, project["id"], [("secret.pdf", pdf_bytes())])

    with caplog.at_level(logging.INFO, logger=LOGGER):
        r = api_client.delete(f"/document/{document['id']}", headers=bearer(token))

    assert r.status_code == 204
    (record,) = [
        r for r in caplog.records if r.name == LOGGER and _field(r, "event") == "document deleted"
    ]
    assert record.levelno == logging.INFO
    assert record.getMessage().startswith("document deleted")
    assert _field(record, "login") == "mila"
    assert _field(record, "user_id") == UUID(user_id)
    assert _field(record, "project_id") == UUID(project["id"])
    assert _field(record, "document_id") == UUID(document["id"])
    assert not any("secret" in str(value) for value in vars(record).values())
