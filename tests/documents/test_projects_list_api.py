from fastapi.testclient import TestClient

from tests.support.auth import bearer, signed_in
from tests.support.documents import docx_bytes, pdf_bytes, uploaded
from tests.support.projects import add_participant, create_project


def test_projects_list_includes_each_projects_documents(
    api_client: TestClient, migrated_database_url: str, storage_bucket: str
) -> None:
    mila_id, mila = signed_in(api_client)
    anna_id, anna = signed_in(api_client, "anna")
    first = create_project(api_client, mila, "First")
    second = create_project(api_client, mila, "Second")
    empty = create_project(api_client, mila, "Empty")
    shared = create_project(api_client, anna, "Shared")
    add_participant(migrated_database_url, shared["id"], mila_id)
    add_participant(migrated_database_url, first["id"], anna_id)
    (a,) = uploaded(api_client, mila, first["id"], [("a.pdf", pdf_bytes("a"))])
    (b,) = uploaded(api_client, anna, first["id"], [("b.docx", docx_bytes("b"))])
    (c,) = uploaded(api_client, mila, second["id"], [("c.pdf", pdf_bytes("c"))])
    (d,) = uploaded(api_client, anna, shared["id"], [("d.pdf", pdf_bytes("d"))])

    r = api_client.get("/projects", headers=bearer(mila))

    assert r.status_code == 200
    by_id = {item["id"]: item["documents"] for item in r.json()}
    assert by_id == {
        first["id"]: [b, a],
        second["id"]: [c],
        empty["id"]: [],
        shared["id"]: [d],
    }
