from uuid import uuid4

from fastapi.testclient import TestClient

from tests.support.auth import bearer, signed_in
from tests.support.documents import docx_bytes, pdf_bytes, uploaded
from tests.support.projects import add_participant, create_project


def test_owner_and_participant_see_documents_newest_first(
    api_client: TestClient, migrated_database_url: str, storage_bucket: str
) -> None:
    _, owner = signed_in(api_client)
    participant_id, participant = signed_in(api_client, "anna")
    project = create_project(api_client, owner)
    other = create_project(api_client, owner, "Other")
    add_participant(migrated_database_url, project["id"], participant_id)
    (older,) = uploaded(api_client, owner, project["id"], [("a.pdf", pdf_bytes("a"))])
    (newer,) = uploaded(api_client, participant, project["id"], [("b.docx", docx_bytes("b"))])
    uploaded(api_client, owner, other["id"], [("c.pdf", pdf_bytes("c"))])

    for token in (owner, participant):
        r = api_client.get(f"/project/{project['id']}/documents", headers=bearer(token))

        assert r.status_code == 200
        assert r.json() == [newer, older]
    assert newer["uploaded_by"]["login"] == "anna"


def test_empty_project_lists_empty(api_client: TestClient, storage_bucket: str) -> None:
    _, token = signed_in(api_client)
    project = create_project(api_client, token)

    r = api_client.get(f"/project/{project['id']}/documents", headers=bearer(token))

    assert r.status_code == 200
    assert r.json() == []


def test_outsider_and_unknown_get_404(api_client: TestClient, storage_bucket: str) -> None:
    _, owner = signed_in(api_client)
    _, stranger = signed_in(api_client, "stranger")
    project = create_project(api_client, owner)
    uploaded(api_client, owner, project["id"], [("a.pdf", pdf_bytes())])

    outsider = api_client.get(f"/project/{project['id']}/documents", headers=bearer(stranger))
    unknown = api_client.get(f"/project/{uuid4()}/documents", headers=bearer(owner))

    assert outsider.status_code == 404
    assert outsider.json() == {"detail": "Project not found"}
    assert unknown.status_code == 404
    assert unknown.json() == {"detail": "Project not found"}
