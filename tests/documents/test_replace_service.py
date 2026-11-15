import psycopg
import pytest
from mypy_boto3_s3.client import S3Client
from sqlalchemy.exc import IntegrityError

from project_hub.core.exceptions import NotFoundError
from project_hub.db.database import Database
from project_hub.documents.entities import PDF_CONTENT_TYPE, Document, NewDocument
from project_hub.documents.service import replace_document
from project_hub.documents.validation import ValidFile
from project_hub.projects.entities import NewProject
from project_hub.storage.s3 import S3FileStorage, create_s3_client
from project_hub.users.entities import NewUser, User
from tests.isolated_settings import IsolatedSettings
from tests.support.documents import pdf_bytes
from tests.support.storage import TEST_S3_REGION, bucket_keys, empty_bucket

pytestmark = pytest.mark.anyio

OLD_KEY = "projects/p/documents/old"


async def _stored_document(
    database: Database, s3_endpoint_url: str, s3_client: S3Client, bucket: str
) -> tuple[S3FileStorage, User, Document]:
    storage = S3FileStorage(
        create_s3_client(
            IsolatedSettings(s3_endpoint_url=s3_endpoint_url, s3_region=TEST_S3_REGION)
        ),
        bucket,
    )
    old_data = pdf_bytes("old")
    await storage.put(OLD_KEY, old_data, PDF_CONTENT_TYPE)
    async with database.unit_of_work() as uow:
        mila = await uow.users.add(NewUser("mila", "hash"))
        project = await uow.projects.add(NewProject(mila.id, "Diploma", ""))
        document = await uow.documents.add(
            NewDocument(project.id, "old.pdf", PDF_CONTENT_TYPE, len(old_data), OLD_KEY, mila.id)
        )
        await uow.commit()
    return storage, mila, document


async def test_database_failure_removes_new_file_and_keeps_old(
    database: Database, s3_endpoint_url: str, s3_client: S3Client, storage_bucket: str
) -> None:
    storage, mila, document = await _stored_document(
        database, s3_endpoint_url, s3_client, storage_bucket
    )
    file = ValidFile(name="x" * 256, content_type=PDF_CONTENT_TYPE, data=pdf_bytes("new"))

    try:
        async with database.unit_of_work() as uow:
            with pytest.raises((IntegrityError, psycopg.errors.CheckViolation)):
                await replace_document(uow, storage, mila, document, file)

        assert bucket_keys(s3_client, storage_bucket) == [OLD_KEY]
        async with database.unit_of_work() as uow:
            assert await uow.documents.get(document.id) == document
    finally:
        empty_bucket(s3_client, storage_bucket)


async def test_document_deleted_meanwhile_is_404_and_new_file_removed(
    database: Database, s3_endpoint_url: str, s3_client: S3Client, storage_bucket: str
) -> None:
    storage, mila, document = await _stored_document(
        database, s3_endpoint_url, s3_client, storage_bucket
    )
    async with database.unit_of_work() as uow:
        assert await uow.projects.delete(document.project_id) is True
        await uow.commit()
    file = ValidFile(name="new.pdf", content_type=PDF_CONTENT_TYPE, data=pdf_bytes("new"))

    try:
        async with database.unit_of_work() as uow:
            with pytest.raises(NotFoundError, match="Document not found"):
                await replace_document(uow, storage, mila, document, file)

        assert bucket_keys(s3_client, storage_bucket) == [OLD_KEY]
    finally:
        empty_bucket(s3_client, storage_bucket)
