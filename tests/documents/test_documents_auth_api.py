import pytest
from fastapi.testclient import TestClient

from tests.support.auth import bearer, signed_in
from tests.support.documents import pdf_bytes, upload
from tests.support.projects import create_project

NOT_MULTIPART = {"Content-Type": "multipart/form-data; boundary=x"}


@pytest.mark.parametrize(
    "headers",
    [pytest.param({}, id="no-header"), pytest.param(bearer("garbage"), id="garbage-token")],
)
def test_upload_requires_token(api_client: TestClient, headers: dict[str, str]) -> None:
    _, token = signed_in(api_client)
    project = create_project(api_client, token)

    r = api_client.post(
        f"/project/{project['id']}/documents",
        headers=headers,
        files=[("files", ("a.pdf", pdf_bytes()))],
    )

    assert r.status_code == 401
    assert r.headers["www-authenticate"] == "Bearer"


def test_upload_with_non_uuid_project_id_is_422(api_client: TestClient) -> None:
    _, token = signed_in(api_client)

    r = upload(api_client, token, "not-a-uuid", [("a.pdf", pdf_bytes())])

    assert r.status_code == 422


def test_upload_body_not_parsed_before_access(api_client: TestClient) -> None:
    _, mila = signed_in(api_client)
    _, stranger = signed_in(api_client, "stranger")
    project = create_project(api_client, mila)
    path = f"/project/{project['id']}/documents"

    without_token = api_client.post(path, headers=NOT_MULTIPART, content=b"not multipart")
    outsider = api_client.post(
        path, headers={**bearer(stranger), **NOT_MULTIPART}, content=b"not multipart"
    )
    owner = api_client.post(
        path, headers={**bearer(mila), **NOT_MULTIPART}, content=b"not multipart"
    )

    assert without_token.status_code == 401
    assert outsider.status_code == 404
    assert outsider.json() == {"detail": "Project not found"}
    assert owner.status_code == 422
