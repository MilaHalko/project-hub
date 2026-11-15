import psycopg
import pytest
from mypy_boto3_s3.client import S3Client
from sqlalchemy.exc import IntegrityError

from project_hub.db.database import Database
from project_hub.documents.entities import PDF_CONTENT_TYPE
from project_hub.documents.service import upload_documents
from project_hub.documents.validation import ValidFile
from project_hub.projects.entities import NewProject
from project_hub.storage.s3 import S3FileStorage, create_s3_client
from project_hub.users.entities import NewUser
from tests.isolated_settings import IsolatedSettings
from tests.support.documents import pdf_bytes
from tests.support.storage import TEST_S3_REGION, bucket_keys, empty_bucket

pytestmark = pytest.mark.anyio


async def test_database_failure_removes_the_files_already_stored(
    database: Database, s3_endpoint_url: str, s3_client: S3Client, storage_bucket: str
) -> None:
    storage = S3FileStorage(
        create_s3_client(
            IsolatedSettings(s3_endpoint_url=s3_endpoint_url, s3_region=TEST_S3_REGION)
        ),
        storage_bucket,
    )
    async with database.unit_of_work() as uow:
        mila = await uow.users.add(NewUser("mila", "hash"))
        project = await uow.projects.add(NewProject(mila.id, "Diploma", ""))
        await uow.commit()
    files = [
        ValidFile(name="a.pdf", content_type=PDF_CONTENT_TYPE, data=pdf_bytes()),
        ValidFile(name="x" * 256, content_type=PDF_CONTENT_TYPE, data=pdf_bytes()),
    ]

    try:
        async with database.unit_of_work() as uow:
            with pytest.raises((IntegrityError, psycopg.errors.CheckViolation)):
                await upload_documents(uow, storage, mila, project.id, files)

        async with database.unit_of_work() as uow:
            assert await uow.documents.list_for_project(project.id) == []
        assert bucket_keys(s3_client, storage_bucket) == []
    finally:
        empty_bucket(s3_client, storage_bucket)
