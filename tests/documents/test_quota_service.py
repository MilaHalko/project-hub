import asyncio

import pytest
from mypy_boto3_s3.client import S3Client

from project_hub.core.exceptions import PayloadTooLargeError
from project_hub.db.database import Database
from project_hub.documents.entities import PDF_CONTENT_TYPE, Document, NewDocument
from project_hub.documents.service import delete_document, get_document, replace_document
from project_hub.documents.validation import ValidFile
from project_hub.projects.entities import NewProject
from project_hub.storage.s3 import S3FileStorage, create_s3_client
from project_hub.users.entities import NewUser, User
from tests.isolated_settings import IsolatedSettings
from tests.support.storage import TEST_S3_REGION, bucket_keys, empty_bucket

pytestmark = pytest.mark.anyio


async def test_delete_waits_for_a_running_upload_and_counts_its_documents(
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
        doomed = await uow.documents.add(
            NewDocument(
                project.id, "a.pdf", PDF_CONTENT_TYPE, 10, "projects/p/documents/a", mila.id
            )
        )
        await uow.projects.refresh_storage_used(project.id)
        await uow.commit()

    try:
        async with database.unit_of_work() as uploading:
            await uploading.projects.lock_storage_used(project.id)
            await uploading.documents.add(
                NewDocument(
                    project.id, "b.pdf", PDF_CONTENT_TYPE, 25, "projects/p/documents/b", mila.id
                )
            )
            async with database.unit_of_work() as deleting:
                task = asyncio.create_task(delete_document(deleting, storage, mila, doomed))
                done, _ = await asyncio.wait({task}, timeout=0.5)
                assert not done
                await uploading.projects.refresh_storage_used(project.id)
                await uploading.commit()
                await asyncio.wait_for(task, timeout=2)

        async with database.unit_of_work() as uow:
            access = await uow.projects.get_for_user(project.id, mila.id)
        assert access is not None
        assert access.project.storage_used_bytes == 25
    finally:
        empty_bucket(s3_client, storage_bucket)


def _storage(s3_endpoint_url: str, bucket: str) -> S3FileStorage:
    return S3FileStorage(
        create_s3_client(
            IsolatedSettings(s3_endpoint_url=s3_endpoint_url, s3_region=TEST_S3_REGION)
        ),
        bucket,
    )


async def _project_with_file(
    database: Database, storage: S3FileStorage, *, size: int, others: int = 0
) -> tuple[User, Document]:
    async with database.unit_of_work() as uow:
        mila = await uow.users.add(NewUser("mila", "hash"))
        project = await uow.projects.add(NewProject(mila.id, "Diploma", ""))
        key = f"projects/{project.id}/documents/original"
        await storage.put(key, b"o" * size, PDF_CONTENT_TYPE)
        document = await uow.documents.add(
            NewDocument(project.id, "a.pdf", PDF_CONTENT_TYPE, size, key, mila.id)
        )
        if others:
            await uow.documents.add(
                NewDocument(
                    project.id, "b.pdf", PDF_CONTENT_TYPE, others, "projects/p/documents/b", mila.id
                )
            )
        await uow.projects.refresh_storage_used(project.id)
        await uow.commit()
    return mila, document


async def test_replace_after_another_replace_discards_that_replace_file(
    database: Database, s3_endpoint_url: str, s3_client: S3Client, storage_bucket: str
) -> None:
    storage = _storage(s3_endpoint_url, storage_bucket)
    mila, document = await _project_with_file(database, storage, size=10)
    try:
        async with database.unit_of_work() as second:
            stale = await get_document(second, mila, document.id)
            async with database.unit_of_work() as first:
                loaded = await get_document(first, mila, document.id)
                await replace_document(
                    first, storage, mila, loaded, ValidFile("one.pdf", PDF_CONTENT_TYPE, b"1" * 20)
                )
            last = await replace_document(
                second, storage, mila, stale, ValidFile("two.pdf", PDF_CONTENT_TYPE, b"2" * 30)
            )

        assert bucket_keys(s3_client, storage_bucket) == [last.storage_key]
        async with database.unit_of_work() as uow:
            assert await uow.documents.get(document.id) == last
            access = await uow.projects.get_for_user(document.project_id, mila.id)
        assert access is not None
        assert access.project.storage_used_bytes == 30
    finally:
        empty_bucket(s3_client, storage_bucket)


async def test_replace_checks_the_limit_against_the_size_left_by_another_replace(
    database: Database, s3_endpoint_url: str, s3_client: S3Client, storage_bucket: str
) -> None:
    storage = _storage(s3_endpoint_url, storage_bucket)
    mila, document = await _project_with_file(database, storage, size=60, others=50)
    try:
        async with database.unit_of_work() as second:
            stale = await get_document(second, mila, document.id)
            async with database.unit_of_work() as first:
                loaded = await get_document(first, mila, document.id)
                shrunk = await replace_document(
                    first,
                    storage,
                    mila,
                    loaded,
                    ValidFile("small.pdf", PDF_CONTENT_TYPE, b"s" * 40),
                    limit_bytes=100,
                )
            with pytest.raises(PayloadTooLargeError):
                await replace_document(
                    second,
                    storage,
                    mila,
                    stale,
                    ValidFile("grown.pdf", PDF_CONTENT_TYPE, b"g" * 55),
                    limit_bytes=100,
                )

        assert bucket_keys(s3_client, storage_bucket) == [shrunk.storage_key]
        async with database.unit_of_work() as uow:
            assert await uow.documents.get(document.id) == shrunk
    finally:
        empty_bucket(s3_client, storage_bucket)
